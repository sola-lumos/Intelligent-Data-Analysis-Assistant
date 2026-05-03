# 智能数据分析助手（DataAnalyticsSystem）

自然语言驱动的数据分析 Web 应用：左侧会话与历史、中间 **ECharts** 可视化、右侧问答；后端 **FastAPI** + **SQLite**，NL2SQL 与洞察基于 **阿里云百炼（DashScope）OpenAI 兼容接口** 与 LangChain。

详细设计见 [docs/智能数据分析系统-模块规划.md](docs/智能数据分析系统-模块规划.md)。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19、Vite、TypeScript、ECharts |
| 后端 | Python 3.9+、FastAPI、LangChain / LangGraph、SQLite |
| 模型 | 百炼 Qwen（`ChatOpenAI` + 兼容 Base URL） |

## 快速开始

### 1. 后端

```bash
make install-backend
cp backend/.env.example backend/.env
# 编辑 backend/.env，填写 DASHSCOPE_API_KEY（以及按需调整 QWEN_MODEL 等）
make test-backend
make dev-backend    # http://127.0.0.1:8000  API 文档：/docs
```

健康检查：`GET /api/health` → `{"status":"ok"}`（具体字段以运行版本为准）。

未配置 `DASHSCOPE_API_KEY` 时，对话相关能力会降级或返回提示；洞察接口会返回 503 说明。

### 2. 前端

```bash
make install-frontend
# 可选：复制 frontend/.env.example 为 frontend/.env.development 并修改后端地址
make test-frontend    # 等价 npm run build
make dev-frontend     # http://localhost:5173
```

默认通过 `VITE_API_BASE_URL`（示例见 `frontend/.env.example`）指向 `http://127.0.0.1:8000`，需与 Uvicorn 地址一致。

### 3. Makefile 摘要

| 命令 | 说明 |
|------|------|
| `make install-backend` | 创建 `backend/.venv` 并安装依赖 |
| `make install-frontend` | `npm install` |
| `make test-backend` | `pytest` |
| `make test-frontend` | 前端生产构建 |
| `make dev-backend` | Uvicorn 热重载 `:8000` |
| `make dev-frontend` | Vite 开发服务器 `:5173` |

## 目录结构（概要）

```
backend/app/          FastAPI、路由、Chat / NL2SQL、会话与洞察
backend/tests/
frontend/src/         DataAnalysisPage、ChartPanel、ChatPanel、Sidebar、API 客户端
data/                 SQLite 数据目录（按需创建）
docs/                 模块与规划文档
```

## 上传到 GitHub 的检查清单

- [ ] 确认 **`backend/.env` 未纳入 Git**（`git status` 中不应出现待提交的 `.env`）。
- [ ] 全仓库搜索不存在 `sk-` 长串等密钥形态（仅示例文档可用 `your_api_key` 等占位）。
- [ ] 大型目录已通过 `.gitignore` 排除：`backend/.venv/`、`frontend/node_modules/`、`frontend/dist/`。
- [ ] 按需添加 **`LICENSE`**、**议题模板**、CI（本项目 Makefile 已便于本地与 Actions 调用）。

## License

未指定时由仓库维护者补充；若开源请在本目录添加 `LICENSE` 文件。
