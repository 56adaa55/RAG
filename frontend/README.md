# MyRAG 前端

MyRAG 检索增强生成系统的前端单页应用，提供 RAG 管道全流程的可视化操作界面。

## 技术栈

- **React 18** — UI 框架
- **Vite 5** — 构建工具
- **Tailwind CSS 3** — 样式方案
- **React Router 7** — 客户端路由
- **React Markdown** — Markdown 渲染

## 页面结构

| 路由 | 页面 | 说明 |
|------|------|------|
| `/load-file` | 文档导入 | 上传 PDF 并选择加载引擎（PyMuPDF / PyPDF / pdfplumber / Unstructured） |
| `/parse-file` | 文件解析 | 结构化解析文档（全文 / 按页 / 按标题 / 标题+表格） |
| `/chunk-file` | 知识分块 | 将文档拆分为文本块（按页 / 固定大小 / 按段落 / 按句子） |
| `/embedding` | 向量存储 | 调用 Embedding 模型生成向量并持久化 |
| `/indexing` | 向量库索引 | 将向量存入 Chroma / Milvus，含索引对比分析功能 |
| `/search` | 相似性检索 | 语义搜索 + 检索前/后优化策略（HyDE / 重排序 / 去重等） |
| `/generation` | 响应生成 | 基于检索上下文调用 LLM 生成回答 |
| `/evaluation` | 检索效果评估 | 上传标注 CSV 评估检索命中率与召回率 |

## 项目结构

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── Sidebar.jsx          # 侧边栏导航
│   │   └── RandomImage.jsx      # 装饰图片组件
│   ├── config/
│   │   └── config.js            # API 地址配置（开发/生产/测试）
│   ├── pages/
│   │   ├── LoadFile.jsx         # 文档导入页
│   │   ├── ParseFile.jsx        # 文件解析页
│   │   ├── ChunkFile.jsx        # 知识分块页
│   │   ├── EmbeddingFile.jsx    # 向量存储页
│   │   ├── Indexing.jsx         # 向量库索引页
│   │   ├── Search.jsx           # 相似性检索页
│   │   ├── Generation.jsx       # 响应生成页
│   │   └── Evaluation.jsx       # 检索效果评估页
│   ├── App.jsx                  # 根组件 + 路由配置
│   ├── App.css
│   ├── index.css                # Tailwind 入口
│   └── main.jsx                 # 应用入口
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── eslint.config.js
```

## 运行

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认启动在 `http://localhost:5174`，后端 API 地址配置在 `src/config/config.js`（默认 `http://localhost:8001`）。

## 构建

```bash
npm run build    # 输出到 dist/
npm run preview  # 预览构建产物
```
