# 智能数据分析助手

开源的自然语言数据分析 Web 应用：左侧会话与历史、中间 **ECharts** 可视化、右侧问答；后端 **FastAPI** + **SQLite**，NL2SQL 与「数据洞察」基于 **阿里云百炼（DashScope）OpenAI 兼容接口** 与 LangChain。

| 资源 | 链接 |
|------|------|
| **源码仓库** | [github.com/sola-lumos/Intelligent-Data-Analysis-Assistant](https://github.com/sola-lumos/Intelligent-Data-Analysis-Assistant) |
| **设计文档** | [docs/智能数据分析系统-模块规划.md](docs/智能数据分析系统-模块规划.md) |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19、Vite、TypeScript、ECharts |
| 后端 | Python 3.9+、FastAPI、LangChain / LangGraph、SQLite |
| 模型 | 百炼 Qwen（`ChatOpenAI` + OpenAI 兼容 Base URL） |

---

## 环境要求

| 依赖 | 说明 |
|------|------|
| **Python** | 3.9 及以上（推荐 3.10+） |
| **Node.js** | 20.x LTS 或其它支持当前 Vite 的版本 |
| **Make** | 可选；未安装时可按下文「不用 Make」手工执行命令 |
| **百炼账号** | 使用对话与洞察功能需在阿里云开通 DashScope 并创建 API Key（可选；不配密钥时部分能力不可用） |

---

## 克隆项目

在终端进入你希望存放代码的目录，任选一种方式：

```bash
# HTTPS
git clone https://github.com/sola-lumos/Intelligent-Data-Analysis-Assistant.git

# SSH（需已在 GitHub 配置 SSH 密钥）
git clone git@github.com:sola-lumos/Intelligent-Data-Analysis-Assistant.git
```

进入项目根目录：

```bash
cd Intelligent-Data-Analysis-Assistant
```

以下命令均在**项目根目录**执行。

---

## 从零运行（推荐：两个终端）

### 第一步：后端

1. **安装依赖**（创建 `backend/.venv` 并安装 Python 包）

   ```bash
   make install-backend
   ```

   **不用 Make 时：**

   ```bash
   cd backend && python3 -m venv .venv
   .venv/bin/pip install -U pip
   .venv/bin/pip install -r requirements-dev.txt
   cd ..
   ```

2. **配置环境变量**

   ```bash
   cp backend/.env.example backend/.env
   ```

   用编辑器打开 **`backend/.env`**，至少配置：

   | 变量 | 说明 |
   |------|------|
   | `DASHSCOPE_API_KEY` | 百炼 API Key；留空则 NL2SQL / 洞察不可用，其它接口仍可探 |
   | `DASHSCOPE_BASE_URL` | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
   | `QWEN_MODEL` | 例如 `qwen-plus`，以控制台实际可用模型名为准 |
   | `SQLITE_DB_PATH` | 默认 `./data/app.db`（相对 `backend` 工作目录）|
   | `CORS_ORIGINS` | 前端开发地址，默认含 `http://localhost:5173` |

   **`backend/.env` 已被 `.gitignore` 忽略，请勿把真实密钥提交到 Git。**

3. **（可选）运行测试**

   ```bash
   make test-backend
   ```

4. **启动 API 服务**

   ```bash
   make dev-backend
   ```

   默认监听：**http://127.0.0.1:8000**

   - Swagger：**http://127.0.0.1:8000/docs**
   - 健康检查：`GET http://127.0.0.1:8000/api/health`

   **不用 Make 时：**

   ```bash
   cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### 第二步：前端

在新的终端窗口中：

1. **安装依赖**

   ```bash
   make install-frontend
   ```

   **不用 Make 时：**

   ```bash
   cd frontend && npm install && cd ..
   ```

2. **（可选）配置后端地址**

   若后端不在 `http://127.0.0.1:8000`，可复制示例并修改：

   ```bash
   cp frontend/.env.example frontend/.env.development
   ```

   编辑 **`frontend/.env.development`** 中的 `VITE_API_BASE_URL`。仓库里若已有 **`frontend/.env.development`**，可直接改其中的地址。

   其它常用变量见 **`frontend/.env.example`**（如 `VITE_USE_SSE_CHAT`）。

3. **启动开发服务器**

   ```bash
   make dev-frontend
   ```

   **不用 Make 时：**

   ```bash
   cd frontend && npm run dev
   ```

4. **浏览器访问**

   打开终端提示的本地地址（一般为 **http://localhost:5173**）。

---

## 使用说明（简要）

1. 在左侧新建或切换会话。
2. 在右侧「问答」输入自然语言问题（指标、维度、时间范围等）。
3. 中间「可视化」展示表格或图表（依赖查询结果与推断规则）。
4. 若已配置大模型且会话正常，可使用「生成数据洞察」等能力。

未配置 `DASHSCOPE_API_KEY` 时：界面仍可加载，但对话可能走本地 Mock 或返回配置提示；洞察接口会返回说明需配置密钥。

---

## Makefile 命令一览

| 命令 | 说明 |
|------|------|
| `make install-backend` | 创建虚拟环境并安装后端依赖 |
| `make install-frontend` | `npm install` |
| `make dev-backend` | Uvicorn 热重载，端口 `8000` |
| `make dev-frontend` | Vite 开发服务器 |
| `make test-backend` | `pytest` |
| `make test-frontend` | 前端生产构建（`npm run build`） |
| `make verify-langchain` | 可选：脚本检测 LangChain / 百炼连通（可能产生计费） |

前端单独检查代码风格：`cd frontend && npm run lint`。

---

## 目录结构

```
backend/app/          FastAPI、路由、Chat / NL2SQL、会话与数据洞察
backend/tests/        pytest
backend/data/         SQLite 目录（本地生成，*.db 不入库）
frontend/src/         React 页面与组件、API 封装
data/                 根目录数据占位（可按部署调整）
docs/                 模块与规划文档
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 前端无法请求后端 | 确认后端已启动；检查 `VITE_API_BASE_URL` 与 `backend/.env` 中 `CORS_ORIGINS` 是否包含前端来源 |
| 对话报错 / 503 | 检查 `DASHSCOPE_API_KEY`、`QWEN_MODEL` 是否与百炼控制台一致 |
| `make` 不可用 | 使用上文「不用 Make」中的等价命令 |
| 端口占用 | 修改 `Makefile` 中 uvicorn 端口或 `vite.config.ts` / 启动参数 |

---

## 安全与开源协作

- **不要**向仓库提交 **`backend/.env`**、任何 **`*.db`** 或真实 API Key。
- 若 Key 曾泄露，请到 [百炼控制台](https://dashscope.console.aliyun.com/) **轮换密钥**。
- 欢迎 Issue / Pull Request；提交前建议本地执行 `make test-backend` 与 `cd frontend && npm run lint && npm run build`。

---

## 许可证（License）
MIT
