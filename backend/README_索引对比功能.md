# 向量库索引对比分析 — 功能说明文档

## 概述

本文档记录在原有 RAG 项目基础上，为完成"**向量库索引比较分析多种不同索引方式**"任务所做的所有修改和新增功能。

---

## 一、原有代码中修复的问题（Bug Fix）

### 1.1 Milvus 索引类型硬编码

**文件**: `services/vector_store_service.py` — `_index_to_milvus()` 方法（原第 341–350 行）

**问题**: 无论用户在界面选择哪种索引模式（flat / ivf_flat / ivf_sq8 / hnsw），Milvus 实际创建的索引始终是 `IVF_FLAT`，参数也硬编码为 `nlist=1280`。

**修复**: 改为调用已有的 `_get_milvus_index_type(config)` 和 `_get_milvus_index_params(config)` 方法，根据 `config.index_mode` 动态选择索引类型。

### 1.2 Provider 分支逻辑 Bug

**文件**: `services/vector_store_service.py` — `index_embeddings()` 方法（原第 168–172 行）

**问题**: 两个独立的 `if` 语句而非 `if/elif`，当 provider 为 Chroma 时仍可能尝试进入 Milvus 分支。

**修复**: 改为 `if/elif/else` 分支。

### 1.3 Milvus Provider 未启用

**文件**: `services/search_service.py` — `get_providers()` 方法（原第 41–44 行）

**问题**: 该接口只返回 Chroma，Milvus 被注释掉。

**修复**: 同时返回 Milvus 和 Chroma 两个 provider。

### 1.4 Milvus 搜索逻辑缺失

**文件**: `services/search_service.py` — `search()` 方法

**问题**: 整个 Milvus 搜索代码被注释掉（原第 228–318 行），使用旧 `Collection` API。

**修复**: 新增 `provider` 参数，使用 `MilvusClient` API 重写了 Milvus 搜索代码。Chroma 搜索逻辑完全不变。

### 1.5 Milvus 集合列表缺失

**文件**: `services/search_service.py` — `list_collections()` 方法

**问题**: 只实现了 Chroma，Milvus 部分被注释。

**修复**: 添加 Milvus 分支，同时修复了 Chroma 分支中 `count` 固定为 1 的问题（改为 `collection.count()`）。

### 1.6 前端 Indexing 页面 Bug 修复

**文件**: `frontend/src/pages/Indexing.jsx`

**问题**:
- Provider 下拉框绑定 `selectedProvider`，但索引模式下拉框绑定 `vectorDb`（旧变量），两者可能不同步
- 发送请求时 `vectorDb` 字段用的是旧状态变量
- URL 模板字符串多了个 `}`：`/collections}` → 返回 404

**修复**: 统一使用 `selectedProvider`，修正 URL。

### 1.7 Search 页面缺少 provider 参数

**文件**: `frontend/src/pages/Search.jsx`

**问题**: 搜索请求未传 `provider` 参数，默认 `selectedProvider` 为 `milvus`（已废弃）。

**修复**: 请求体中添加 `provider: selectedProvider`，默认值改为 `chroma`。

### 1.8 后端启动依赖全量导入

**文件**: `backend/main.py`

**问题**: 原代码在模块顶层导入所有服务类，只要一个依赖包缺失整个服务器就无法启动。

**修复**: 改为懒加载模式——通过 `_get_service()` 函数按需导入，首次调用某服务时才加载对应模块。

### 1.9 loading_service.py 顶层导入导致崩溃

**文件**: `backend/services/loading_service.py`

**问题**: 顶部导入了 `pypdf`、`unstructured`、`pdfplumber` 等重型库。`unstructured` 缺少 `unstructured_inference` 等依赖时，即使选择 PyMuPDF 方式加载也会因导入失败而崩溃。

**修复**: `pypdf`、`unstructured`、`pdfplumber` 改为方法内部懒加载（用时才导入），只保留 `fitz`（PyMuPDF）为顶层导入（默认方式所需）。

### 1.10 chunking_service.py 导入路径过时

**文件**: `backend/services/chunking_service.py`

**问题**: `from langchain.text_splitter import ...` 在新版 LangChain 中已废弃，`text_splitter` 被拆分到独立包 `langchain_text_splitters`。

**修复**: 改为 `from langchain_text_splitters import RecursiveCharacterTextSplitter`。

### 1.11 generation_service.py 缺少依赖

**文件**: `backend/services/generation_service.py`

**问题**: `langchain_huggingface` 未安装，导致导入 GenerationService 时报错（虽不直接影响索引对比任务）。

**修复**: 安装 `langchain-huggingface` 包。

---

## 二、新增功能

### 2.1 FAISS 向量库配置预留

**文件**: `backend/utils/config.py`

在 `VectorDBProvider` 枚举中添加 `FAISS`，并新增配置字典 `FAISS_CONFIG`（含 flat/ivf/hnsw 索引类型及参数），为后续扩展做准备。

### 2.2 搜索延迟统计

**文件**: `backend/services/search_service.py` — `search()` 方法

每次搜索返回结果中新增 `search_latency_ms` 字段，记录毫秒级耗时。

### 2.3 索引对比分析服务（核心新功能）

**新文件**: `backend/services/comparison_service.py`

`ComparisonService.run_comparison()` 自动化流程：

```
选择嵌入文件 → 对每种 (provider, index_mode) 组合:
    1. 索引到对应向量库 → 记录索引时间、索引大小
    2. 运行全部查询 → 记录每条查询的延迟、命中结果
    3. 计算平均搜索延迟、命中率(score_hit)、覆盖率(score_find)
→ 输出对比矩阵
```

**容错设计**: 某个索引配置失败时（如 Milvus 未启动），不会中断整个对比，失败的配置标记 `index_error` 并跳过搜索环节。

### 2.4 对比分析 API 端点

**文件**: `backend/main.py`

| 端点 | 方式 | 说明 |
|------|------|------|
| `POST /compare` | JSON | 直接传查询列表进行对比 |
| `POST /compare/from-csv` | CSV 上传 | 上传 CSV（格式同 `/evaluate`）进行对比 |

同时 `/search` 和 `/evaluate` 端点新增 `provider` 参数，支持指定向量库。

### 2.5 前端对比分析页面

**新文件**: `frontend/src/pages/Comparison.jsx`
**路由**: `/comparison`
**导航**: 侧边栏新增"索引对比"

**页面功能**:
- 左侧：选择嵌入文件、多选索引配置、文本/CSV 查询输入、参数调节
- 右侧：汇总对比表（最优值绿色高亮）、搜索延迟条形图、命中率条形图、逐查询详情展开

---

## 三、使用方式

### 前置条件

1. 确保已有嵌入文件（流程：加载 → 分块 → 嵌入产出，存放于 `02-embedded-docs/`）
2. Chroma 无需额外配置，内嵌运行，数据自动持久化到 `03-vector-store/chromadb/`
3. Milvus 需额外安装 Docker 并运行 Milvus 服务（`localhost:19530`），**未安装时不影响 Chroma 对比**
4. 嵌入模型选择 **HuggingFace** 无需 API Key，免费本地运行

### 启动命令

**后端**（终端1，必须用 `py` 而非 `python`）：
```powershell
cd "D:\数据挖掘课项目\RAG-main\RAG-main\backend"
py -m uvicorn main:app --reload --port 8001
```

**前端**（终端2）：
```powershell
cd "D:\数据挖掘课项目\RAG-main\RAG-main\frontend"
npm run dev
```

浏览器打开前端地址（终端输出中确认，通常 `http://localhost:5173`）。

### 操作流程

1. **文档导入** → 上传 PDF，加载方式选 **PyMuPDF**
2. **知识分块** → 选文档，分块方式选 `by_pages` 或 `fixed_size`
3. **向量存储** → 选嵌入提供者 **HuggingFace**，模型选 `all-MiniLM-L6-v2`
4. **索引对比** → 选嵌入文件，勾选 Chroma 的 hnsw 和 standard 两种模式 → 输入查询 → 运行对比

### Chroma 对比方案（无需 Milvus）

勾选以下配置即可完成对比分析：

| provider | index_mode | 说明 |
|----------|-----------|------|
| chroma | hnsw | 基于图的近似最近邻（速度快） |
| chroma | standard | 标准模式（精度高） |

配合不同嵌入模型（bge-small-zh / all-MiniLM / all-mpnet）做交叉对比，同样能产出完整的分析报告。

### API 调用

```powershell
$body = @{
    embedding_file = "your_file.json"
    index_configs = @(
        @{provider="chroma"; index_mode="hnsw"},
        @{provider="chroma"; index_mode="standard"}
    )
    queries = @(@{query_text="测试查询"; expected_pages=@(1)})
    top_k = 5
    threshold = 0.7
} | ConvertTo-Json -Depth 4

Invoke-WebRequest -Uri "http://localhost:8001/compare" `
    -Method POST -ContentType "application/json" -Body $body
```

### Swagger 文档

打开 `http://localhost:8001/docs`，找到 `POST /compare`，直接在页面上填写参数执行。

### 结果保存

对比结果自动保存到 `07-comparison-results/`，JSON 格式。

---

## 四、修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/utils/config.py` | 修改 | 添加 FAISS 枚举和配置，修复 MILVUS 枚举逗号 Bug |
| `backend/services/vector_store_service.py` | 修改 | 解除索引类型硬编码，修复 if/elif 分支 |
| `backend/services/search_service.py` | 修改 | 启用 Milvus + 集合列表 + 搜索逻辑 + 延迟计时 |
| `backend/services/loading_service.py` | 修改 | 重型依赖改为懒加载（pypdf/unstructured/pdfplumber 用时才导入） |
| `backend/services/chunking_service.py` | 修改 | `langchain.text_splitter` → `langchain_text_splitters` |
| `backend/services/comparison_service.py` | **新建** | 索引对比分析核心服务 |
| `backend/main.py` | 修改 | 懒加载改造 + 新增 `/compare` `/compare/from-csv` + 各端点添加 provider 参数 + 错误处理改进 |
| `frontend/src/pages/Indexing.jsx` | 修改 | 修复 provider/indexMode 变量不一致 + URL 拼写 Bug |
| `frontend/src/pages/Search.jsx` | 修改 | 添加 provider 参数，默认 chroma |
| `frontend/src/pages/Comparison.jsx` | **新建** | 索引对比分析页面 |
| `frontend/src/App.jsx` | 修改 | 添加 `/comparison` 路由 |
| `frontend/src/components/Sidebar.jsx` | 修改 | 添加"索引对比"导航项 |

---

## 五、对原有功能的影响

**无破坏性影响**。所有修改均保持向后兼容：

- **懒加载改造**：功能等价，服务实例仍是单例，只是延迟到首次使用时初始化
- **索引类型修复**：对原有 Chroma 流程无影响；Milvus 从硬编码变为按选择动态切换
- **搜索改造**：Chroma 搜索逻辑一行未改，仅新增 provider 路由参数
- **依赖懒加载**：`loading_service.py` 中 pypdf/unstructured/pdfplumber 改为方法内导入，PyMuPDF 不受影响
- **导入路径修复**：`chunking_service.py` 适配新版 LangChain，行为不变
- **新增文件**：纯增量，不影响已有功能
