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
- Python 3.8+ (用于后端)

### 后端运行

1. 进入后端目录：
   ```bash
   cd backend
   ```
2. 安装依赖（根据所需环境安装对应的 Python 包）：
   ```bash
   pip install fastapi uvicorn pandas python-multipart
   # 以及其他项目中实际使用的 RAG 相关依赖
   ```
3. 运行 FastAPI 服务：
   ```bash
   uvicorn main:app --reload
   ```
   后端服务将在 `http://localhost:8000` 启动。

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
   前端页面将通过 Vite 提供的地址访问（通常是 `http://localhost:5173`）。

## 使用指南

1. 在浏览器中打开前端应用。
2. 按照侧边栏导航从上到下依次操作：
   - 首先在 **Load File (加载)** 页面上传文档。
   - 接下来对文档进行 **Parse (解析)** 和 **Chunk (分块)**。
   - 进入 **Embedding (向量化)** 将文本块转换为向量。
   - 使用 **Indexing (索引)** 将其存储在所选的向量数据库中。
   - 在 **Search (检索)** 页面测试您的文档检索效果。
   - 最后，使用 **Generation (生成)** 页面提出问题，基于上传的文档生成 AI 回答！
