# MyRAG

MyRAG 是一个端到端的检索增强生成 (RAG) 系统，提供了一个包含文档处理、向量化、索引构建、检索以及答案生成的完整工作流。系统配备了完善的可视化界面，引导用户完成 RAG 生命周期的每一步。

## 功能特性与工作流

本应用围绕 RAG 管道的核心阶段进行构建：

1. **文档加载 (Document Loading)**：上传并使用多种策略加载文档（如 PDF 等）。
2. **解析 (Parsing)**：解析已加载的文档以提取文本和结构。
3. **分块 (Chunking)**：将文档拆分为便于管理的文本块，以便进行有效的向量化和检索。
4. **向量化 (Embedding)**：使用各种 Embedding 模型为文本块生成向量。
5. **索引构建 (Indexing)**：将生成的向量存储到向量数据库（例如 Chroma、Milvus）中，实现快速的相似度检索。
6. **检索 (Search)**：查询向量数据库，基于语义相似度检索最相关的文档块。
7. **生成 (Generation)**：使用大型语言模型 (LLM)，基于检索到的上下文生成连贯且准确的回答。

## 项目结构

本项目主要由两部分组成：

- **`backend/`**：基于 Python FastAPI 的后端服务器，处理 RAG 的核心逻辑。
  - 可扩展的服务架构（包含 `LoadingService`, `ParsingService`, `ChunkingService`, `EmbeddingService`, `VectorStoreService`, `SearchService`, `GenerationService`）。
  - 用于存储中间状态的本地文件管理系统（如 `01-loaded-docs`, `01-chunked-docs`, `02-embedded-docs` 等）。
  - 为整个处理管道的每个步骤提供了相应的 API 接口。

- **`frontend/`**：基于 React、Vite 和 Tailwind CSS 构建的单页前端应用。
  - 带有侧边栏导航的交互式用户界面。
  - 为 RAG 管道的每个步骤提供了专属页面（`/load-file`, `/chunk-file`, `/parse-file`, `/embedding`, `/indexing`, `/search`, `/generation`）。

## 技术栈

**后端**
- Python 3
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- Pandas - 数据处理与评估

**前端**
- [React 18](https://react.dev/)
- [Vite](https://vitejs.dev/)
- [React Router](https://reactrouter.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- React Markdown

## 快速开始

### 环境要求
- Node.js & npm (用于前端)
- Python 3.10 (用于后端)

### 后端运行

1. 进入后端目录：
   ```bash
   cd backend
   ```
2. 安装依赖（根据所需环境安装对应的 Python 包）：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
RAG系统环境变量配置示例，后端启动前在同一终端运行以下指令来配置相应的环境变量
   ```bash
   $env:DASHSCOPE_API_KEY="你的apikey"
   ```

#### OpenAI配置（用于嵌入和生成）
OPENAI_API_KEY=sk-your-openai-api-key-here

#### 阿里云百炼配置（用于生成）
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here

#### DeepSeek配置（用于生成）
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here

#### HuggingFace本地模型路径（可选）
如果不配置，将从HuggingFace Hub下载模型
HF_MODEL_PATH=/path/to/your/local/huggingface/models


4. 运行 FastAPI 服务：
   ```bash
   uvicorn main:app --reload --port 8001 --host 0.0.0.0
   ```
   后端服务将在 `http://localhost:8001` 启动。

### 前端运行

1. 进入前端目录：
   ```bash
   cd frontend
   ```
2. 安装依赖：
   ```bash
   npm install
   ```
3. 启动开发服务器：
   ```bash
   npm run dev
   ```
   前端页面将通过 Vite 提供的地址访问（通常是 `http://localhost:5174`）。

## 使用指南

1. 在浏览器中打开前端应用。
2. 按照侧边栏导航从上到下依次操作：
   - 首先在 **Load File (加载)** 页面上传文档。
   - 接下来对文档进行 **Parse (解析)** 和 **Chunk (分块)**。
   - 进入 **Embedding (向量化)** 将文本块转换为向量。
   - 使用 **Indexing (索引)** 将其存储在所选的向量数据库中。
   - 在 **Search (检索)** 页面测试您的文档检索效果。
   - 最后，使用 **Generation (生成)** 页面提出问题，基于上传的文档生成 AI 回答！

## 开发项目概览

**1. 前端增加功能**（frontend/src/）
```javascript
new_feature：新增前端“检索效果评估”页，并接入导航
- 改动位置：
-- 新页面：Evaluation.jsx (line 1)
-- 新路由 /evaluation：App.jsx (line 12)
-- 侧边栏入口“检索效果评估”：Sidebar.jsx (line 16)

- 页面功能：
-- 上传评估 CSV 文件
-- 选择向量库 provider 和 collection
-- 设置 top_k、相似性阈值
-- 调用后端 /evaluate
-- 展示平均命中分、平均找回分、有效查询数
-- 展示每条 query 的 expected pages、found pages、score hit、score find


fix：修复后端 /evaluate 接口的检索结果解析逻辑
- 在 backend/main.py (line 783) 中兼容新的搜索返回结构，从 search_response["results"] 中提取检索结果。
- 页码解析兼容 metadata.page 和 metadata.page_number 两种字段。
- 对无效页码做容错，避免单条结果导致整行评估失败。
- 保持原有输出结构不变，仍返回 results、average_scores、total_queries 和 parameters。

```

**2. 文件解析细化**（backend/services/parsing_service.py）

**更新说明：新增 `_parse_titles_and_tables` 方法**
本次更新对 `parsing_service.py` 进行了优化，主要新增了 `_parse_titles_and_tables` 方法，以实现对 PDF 中标题、正文、表格和图表的精确混合解析。
* **多维度标题识别 (`is_title`)**：排除了特殊的数学干扰行，支持匹配常见章节格式，并兼容底层工具的 "Title" 标记。
* **图表与说明文本智能拼接**：自动识别图表说明，重新与对应的图表块拼接，防止分离；并优先保留表格的 HTML 属性。
* **跨图表段落合并**：在同一个章节标题下，如果正文内容被表格或图表物理打断，会在处理尾声重新合并属于同一个标题的离散正文段落。

**3. 向量索引比较**（新增 backend/services/index_benchmark.py）
```python
# 从RAGSystem_Enhanced移植：
- FAISS Flat索引
- FAISS IVF索引
- FAISS LSH索引
- 性能对比测试
- 生成对比报告
```

**4. 检索优化**（backend/services/）
```python
# 添加优化服务：
- query_optimizer_service.py      # 检索前：查询改写、多查询生成
- reranker_service.py             # 检索后：重排序
- deduplication_service.py        # 检索后：语义去重
