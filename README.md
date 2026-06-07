# Java 全文搜索引擎说明

本项目是一个基于 Spring Boot + Elasticsearch 的全文搜索应用，核心页面是：

```text
http://localhost:8080/contentse
```

该页面面向问答数据搜索，支持用户输入自然语言问题或关键词表达，后端通过关键词召回、语义向量召回、RRF 融合和重排序返回相关问题与答案。

## 核心入口

### 全文搜索页面

```text
http://localhost:8080/contentse
```

前端页面文件：

```text
src/main/resources/templates/se.html
```

该页面会向后端接口发送请求：

```text
POST /queryAll
```

对应后端方法：

```text
src/main/java/com/example/demo/controller/ContentController.java
src/main/java/com/example/demo/service/ContentService.java
```

### 数据写入接口

首次使用或修改数据、向量字段后，需要访问：

```text
http://localhost:8080/writeQA
```

该接口会读取：

```text
D:/信息检索/questions2.json
D:/信息检索/answers2.json
```

并写入 Elasticsearch 索引：

```text
question2
answer2
```

同时会为问题和答案生成向量字段：

```text
question_vector_qwen_v3
answer_vector_qwen_v3
```

## 运行前准备

### 1. 启动 Elasticsearch

项目默认连接本机 Elasticsearch：

```text
127.0.0.1:9200
```

启动后应能访问：

```text
http://localhost:9200
```

如果该页面打不开，搜索和 `/writeQA` 都会失败。

### 2. 配置 DashScope API Key

项目支持调用 Qwen 的：

```text
text-embedding-v3
qwen3-rerank
```

在启动 Spring Boot 的同一个 PowerShell 窗口中配置：

```powershell
$env:DASHSCOPE_API_KEY="你的 DashScope API Key"
```

可选模型配置：

```powershell
$env:DASHSCOPE_EMBEDDING_MODEL="text-embedding-v3"
$env:DASHSCOPE_RERANK_MODEL="qwen3-rerank"
```

如果不配置 API Key，项目仍可运行，但会降级为本地 embedding 和本地排序，语义效果会弱一些。

### 3. 启动 Spring Boot

```powershell
.\mvnw.cmd spring-boot:run
```

如果遇到旧 Lombok 与新版 JDK 的模块访问问题，先执行：

```powershell
$env:MAVEN_OPTS='--add-opens jdk.compiler/com.sun.tools.javac.processing=ALL-UNNAMED'
.\mvnw.cmd spring-boot:run
```

### 4. 写入问答数据

项目启动后访问：

```text
http://localhost:8080/writeQA
```

返回 `true` 表示写入成功。

之后访问：

```text
http://localhost:8080/contentse
```

即可使用全文搜索。

## `/contentse` 的搜索设计

`/contentse` 页面对应的是全局问答搜索。用户输入 query 后，后端会同时搜索问题库和答案库，再统一排序。

整体流程：

```text
用户 query
-> 问题 BM25 召回
-> 答案 BM25 召回
-> 问题 Qwen embedding 向量召回
-> 答案 Qwen embedding 向量召回
-> RRF 合并候选
-> 问题/答案分别归一化
-> qwen3-rerank 重排
-> 返回前端展示
```

### BM25 关键词召回

问题索引 `question2` 使用字段：

```text
qzh      权重 4.0
qen      权重 1.0
qdomain  权重 1.5
```

答案索引 `answer2` 使用字段：

```text
azh      权重 4.0
aen      权重 1.0
```

后端使用 Elasticsearch 的 `simpleQueryStringQuery`，支持一些高级查询语法：

```text
+       必须包含
|       或者
-       排除
" "     精确短语
```

例如：

```text
Java +多线程
前端 | 后端
Python -爬虫
"词袋模型"
```

### Qwen embedding 向量召回

项目会使用 `text-embedding-v3` 将 query、问题文本、答案文本转成 1024 维向量。

问题向量文本：

```text
qzh + qdomain
```

答案向量文本：

```text
azh + qzh + qdomain
```

搜索时使用 Elasticsearch `dense_vector` 和 `cosineSimilarity` 做语义召回。这样即使用户输入的词没有完全命中文档，也可以召回语义相近的内容。

### RRF 融合

BM25 和向量召回的分数分布不同，不能直接相加。

项目使用 RRF，将不同召回通道的排名转成统一的融合分：

```text
rrf_score = 1 / (k + rank)
```

这样可以降低某一种召回方式分数过大导致结果被压制的问题。

### qwen3-rerank 重排

RRF 融合后，项目会对前若干个候选结果调用 `qwen3-rerank`。

rerank 会判断：

```text
用户 query 与候选问题/答案文本是否真正相关
```

最终前端展示的 `score` 是综合排序分，不是单纯 BM25 分，也不是单纯向量相似度。

### `/contentse` 分数计算方式

`/contentse` 面向“用户输入 query 后，在全库中找相关问题和答案”。它的分数目标是衡量：

```text
当前搜索结果与用户 query 的整体相关性
```

整体架构：

```text
用户 query
-> BM25 召回
-> Qwen embedding 向量召回
-> RRF 融合
-> qwen3-rerank
-> score
```

在代码中，问题结果和答案结果会分别先计算 `combined_score`，然后再做类型内归一化和 RRF 融合，最终写入：

```text
final_score
score
```

也就是说，前端 `/contentse` 页面展示的：

```text
score: 0.xxx
```

是最终全局搜索排序分。

#### 问题结果分数

问题结果主要来自：

```text
BM25/RRF 召回分
Qwen embedding 向量分
轻量语义重合分
关键词覆盖分
```

当前问题结果的 `combined_score` 公式为：

```text
combined_score =
normalized_score * 0.45
+ normalized_vector_score * 0.30
+ semanticScore * 0.15
+ coverageBoost * 0.10
```

含义：

```text
normalized_score
    BM25 与向量召回经过 RRF 融合后的归一化分。

normalized_vector_score
    Qwen embedding 向量召回分的归一化结果。

semanticScore
    本地轻量语义重合分，基于中文 n-gram/token 交集。

coverageBoost
    query 中关键词在问题标题/领域中的覆盖比例。
```

#### 答案结果分数

答案结果主要来自：

```text
BM25/RRF 召回分
Qwen embedding 向量分
所属问题相关分
答案与 query 的轻量语义分
答案质量分
低质量惩罚
```

当前答案结果的 `combined_score` 公式为：

```text
combined_score =
normalized_score * 0.35
+ normalized_vector_score * 0.30
+ parentQuestionScore * 0.15
+ answerSemanticScore * 0.10
+ qualityScore * 0.10
+ exactCoreBoost
- qualityPenalty
```

含义：

```text
normalized_score
    BM25 与向量召回经过 RRF 融合后的归一化分。

normalized_vector_score
    Qwen embedding 向量召回分的归一化结果。

parentQuestionScore
    该答案所属问题在当前 query 下的相关分。

answerSemanticScore
    query 与答案正文的轻量语义重合分。

qualityScore
    答案长度质量与答案-问题一致性的组合分。

exactCoreBoost
    query 核心词被答案正文完整包含时的额外奖励。

qualityPenalty
    对过短、空泛或明显低质量答案的惩罚。
```

#### 全局最终分

问题和答案分别算出 `combined_score` 后，会在各自类型内部做归一化，并加入 RRF 排名分：

```text
final_score =
type_normalized_score * 0.85
+ type_rrf_score * 0.15
```

之后如果 DashScope API Key 可用，会对前若干候选调用 `qwen3-rerank`。重排后最终分会进一步更新为：

```text
final_score =
rerank_score * 0.80
+ original_final_score * 0.20
```

最后返回给前端时：

```text
score = final_score
```

## 详情页答案排序

在 `/contentse` 中点击问题或答案，会进入某个问题的答案详情页：

```text
/searchAn/{qid}
```

该页面中的“相关度得分”来自 `searchAnswer(qid)`。

当前详情页排序也已优化为：

```text
已知 qid
-> 读取该问题对应的 qanswers
-> 只在这些候选答案中排序
-> BM25 分
-> Qwen embedding 相似度
-> qwen3-rerank 分
-> 答案质量分
-> 低质量惩罚
```

### `/searchAn/{qid}` 分数计算方式

`/searchAn/{qid}` 面向“已经确定某个问题后，在该问题对应的候选答案里找最佳答案”。它的分数目标是衡量：

```text
某个答案是否真正适合作为该问题的答案
```

整体架构：

```text
问题文本
-> 限定 qanswers 候选答案
-> BM25
-> Qwen embedding
-> qwen3-rerank
-> 答案质量分
-> algorithm_score
```

这里不会全库搜索答案，而是先从问题文档的 `qanswers` 字段取出候选答案 ID，只在这些候选答案中排序。

对应的 `algorithm_score` 由以下部分组成：

```text
algorithm_score =
normalized_bm25_score * 0.25
+ normalized_embedding_score * 0.25
+ normalized_rerank_score * 0.30
+ normalized_semantic_score * 0.10
+ qualityScore * 0.10
- qualityPenalty
```

含义：

```text
normalized_bm25_score
    问题文本与答案正文的 Elasticsearch BM25 匹配分。

normalized_embedding_score
    问题文本向量与答案向量的 Qwen embedding 余弦相似分。

normalized_rerank_score
    qwen3-rerank 对“问题-答案”匹配质量的重排分。

normalized_semantic_score
    本地轻量语义重合分，作为外部模型失败时的补充信号。

qualityScore
    答案长度质量与答案是否贴合问题标题的组合分。

qualityPenalty
    对过短、空泛或明显低质量答案的惩罚。
```

因此：

```text
/contentse 中的 score
```

表示全局搜索排序分；

```text
/searchAn/{qid} 中的相关度得分
```

表示某个问题下候选答案之间的匹配质量分。

两者不是同一个公式，不能直接比较数值大小。

## 常见问题

### `/contentse` 搜索失败

优先检查：

```text
http://localhost:9200
```

如果打不开，说明 Elasticsearch 没启动。

### `/writeQA` 出现 Whitelabel Error Page

常见原因：

```text
Elasticsearch 未启动
DashScope API Key 无效
网络无法访问 DashScope
JSON 数据文件路径不正确
ES 索引字段映射冲突
```

先看启动 Spring Boot 的 PowerShell 控制台，那里会有具体异常。

### 修改代码后页面没有变化

Java 代码修改后需要重启 Spring Boot：

```powershell
Ctrl + C
.\mvnw.cmd spring-boot:run
```

如果修改了数据写入逻辑或向量字段，建议重新访问：

```text
http://localhost:8080/writeQA
```

### API Key 已配置但似乎没有生效

环境变量必须在启动 Spring Boot 的同一个 PowerShell 窗口中设置：

```powershell
$env:DASHSCOPE_API_KEY="你的 DashScope API Key"
.\mvnw.cmd spring-boot:run
```

如果先启动项目，再设置环境变量，项目读不到，需要重启。

## 主要代码位置

```text
src/main/java/com/example/demo/service/ContentService.java
```

核心方法：

```text
searchAllQA(...)        /contentse 全文搜索主流程
searchQuestionCandidates(...)
searchAnswerCandidates(...)
mergeRecallCandidates(...)
applyQwenRerank(...)
searchAnswer(...)       /searchAn/{qid} 答案详情页排序
writeQAContent(...)     写入问题、答案和向量字段
```

前端页面：

```text
src/main/resources/templates/se.html
src/main/resources/templates/answer.html
```
