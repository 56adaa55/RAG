# 代码修改详细说明（相对原始版本）

本文档列出相比项目原始代码所有被修改的文件及具体改动内容。

---

## 1. `backend/utils/config.py`

| 行 | 改动 | 说明 |
|----|------|------|
| 5-7 | `MILVUS = "milvus",` → `MILVUS = "milvus"` | 修复枚举定义中多余的逗号（Python 会把 `"milvus",` 解析为 tuple） |
| 7 | 新增 `FAISS = "faiss"` | 添加 FAISS 向量库枚举值 |
| 末尾 | 新增 `FAISS_CONFIG = {...}` | 添加 FAISS 索引类型和参数配置 |

---

## 2. `backend/services/vector_store_service.py`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 168-172 | 两个独立 `if` → `if/elif/else` | 修复 provider 分支逻辑，新增不支持 provider 时的报错 |
| 341-350 | 硬编码 `index_type="IVF_FLAT"` `params={"nlist": 1280}` → 调用 `_get_milvus_index_type(config)` 和 `_get_milvus_index_params(config)` | 索引类型改为根据 `config.index_mode` 动态选择 |

---

## 3. `backend/services/search_service.py`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 41-44 | `get_providers()` 只返回 Chroma → 同时返回 Milvus 和 Chroma | 启用 Milvus provider |
| 46-90 | `list_collections()` 只有 Chroma → 新增 Milvus 分支 | 支持列出 Milvus 集合；Chroma 分支的 `count` 从硬编码 1 改为 `collection.count()` |
| 133-345 | `search()` 整体重写 | ① 新增 `provider` 参数 ② 保留 Chroma 搜索逻辑不变 ③ 恢复并重写 Milvus 搜索逻辑（使用 `MilvusClient` API 替代旧 `Collection` API） ④ 新增搜索计时 `search_latency_ms` |

---

## 4. `backend/services/loading_service.py`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 1-3 | 顶层导入 `pypdf`、`unstructured`、`pdfplumber` → 移除 | 避免缺失某个依赖导致整个服务崩溃 |
| `_load_with_pypdf()` | 方法内新增 `from pypdf import PdfReader` | 懒加载，用时才导入 |
| `_load_with_unstructured()` | 方法内新增 `from unstructured.partition.pdf import partition_pdf` | 懒加载 |
| `_load_with_pdfplumber()` | 方法内新增 `import pdfplumber` | 懒加载 |

---

## 5. `backend/services/chunking_service.py`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 3 | `from langchain.text_splitter import RecursiveCharacterTextSplitter` → `from langchain_text_splitters import RecursiveCharacterTextSplitter` | 适配新版 LangChain（text_splitter 已被拆分到独立包） |

---

## 6. `backend/services/comparison_service.py` — **新文件**

完整的 `ComparisonService` 类，提供 `run_comparison()` 方法：
- 输入：嵌入文件路径 + 多个 `{provider, index_mode}` 配置 + 查询列表
- 输出：每种配置的索引时间、索引大小、搜索延迟、命中率、覆盖率的对比矩阵
- 容错：单个配置失败不影响其他配置的对比

---

## 7. `backend/main.py`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 6-17 | 所有服务类顶层导入 → 移除 | 改为懒加载，避免一个依赖缺失导致全部无法启动 |
| 新增 | `_get_service()` 函数 | 按需导入并缓存服务实例，支持所有服务及配置类 |
| `/load` 端点 | `LoadingService()` → `_get_service("loading")` | 懒加载 |
| `/load` 端点 | `except: raise` → `raise HTTPException(500, detail=str(e))` | 错误信息不再被吞掉 |
| `/embed` 端点 | `EmbeddingService()` → `_get_service("embedding")` | 懒加载 |
| `/index` 端点 | `VectorStoreService()` → `_get_service("vector_store")` | 懒加载 |
| `/providers` | `SearchService()` → `_get_service("search")` | 懒加载 |
| `/collections` | 同上 | 懒加载 |
| `/search` 端点 | 新增 `provider: str = Body(...)` 参数 | 支持指定向量库搜索 |
| `/evaluate` 端点 | 新增 `provider: str = Form(...)` 参数 | 支持指定向量库评估 |
| 新增 | `POST /compare` 端点 | JSON 方式对比分析 |
| 新增 | `POST /compare/from-csv` 端点 | CSV 上传方式对比分析 |
| 所有 service 端点 | `LoadingService()` → `_get_service("loading")` 等 | 统一改为懒加载 |
| 所有 service 端点 | `ChunkingService()` → `_get_service("chunking")` 等 | 统一改为懒加载 |
| 所有 service 端点 | `ParsingService()` → `_get_service("parsing")` 等 | 统一改为懒加载 |
| 所有 service 端点 | `GenerationService()` → `_get_service("generation")` 等 | 统一改为懒加载 |

---

## 8. `frontend/src/pages/Indexing.jsx`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 51 | `dbConfigs[vectorDb].modes[0]` → `dbConfigs[selectedProvider].modes[0]` | useEffect 依赖修正 |
| 93 | `` `${apiBaseUrl}/collections}` `` → `` `${apiBaseUrl}/collections` `` | 修复 URL 多余 `}` 导致 404 |
| 117 | `vectorDb: vectorDb` → `vectorDb: selectedProvider` | 请求体字段修正 |
| 234 | `dbConfigs[vectorDb].modes` → `dbConfigs[selectedProvider].modes` | 下拉框绑定修正 |

---

## 9. `frontend/src/pages/Search.jsx`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 15 | `useState('milvus')` → `useState('chroma')` | 默认 provider 改为 chroma |
| 50-57 | 请求体新增 `provider: selectedProvider` | 适配后端新增的 provider 参数 |

---

## 10. `frontend/src/pages/Comparison.jsx` — **新文件**

索引对比分析页面，包含：
- 嵌入文件选择、索引配置多选
- 文本/CSV 两种查询输入方式
- 汇总对比表（最优值高亮）
- 搜索延迟和命中率条形图（纯 CSS）
- 逐查询详情展开

---

## 11. `frontend/src/App.jsx`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 12 | 新增 `import Comparison from './pages/Comparison'` | 导入新页面 |
| 28 | 新增 `<Route path="/comparison" element={<Comparison />} />` | 注册路由 |

---

## 12. `frontend/src/components/Sidebar.jsx`

| 行（原） | 改动 | 说明 |
|-----------|------|------|
| 15 | 新增 `{ to: "/comparison", text: "索引对比" }` | 侧边栏导航项 |

---

## 依赖安装（额外操作）

以下包为运行所必需，已在调试过程中安装：

| 包名 | 用途 |
|------|------|
| `langchain` | chunking_service 依赖 |
| `langchain-huggingface` | generation_service 依赖 |
| `unstructured` | loading_service 可选方式 |
| `unstructured_inference` | unstructured 的子依赖 |
| `pi_heif` | unstructured 的子依赖 |

> 注意：本机 Python 命令为 `py` 而非 `python`（`python` 指向 Windows 应用商店占位符）。

---

## 启动方式

```powershell
# 终端1 — 后端
cd "D:\数据挖掘课项目\RAG-main\RAG-main\backend"
py -m uvicorn main:app --reload --port 8001

# 终端2 — 前端
cd "D:\数据挖掘课项目\RAG-main\RAG-main\frontend"
npm run dev
```
