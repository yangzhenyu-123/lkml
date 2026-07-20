# LKML 性能优化专利挖掘平台

> 自动同步 LKML 全量邮件，识别未合入的性能优化提案，借助 OpenCode + [patent-disclosure-skill](https://github.com/handsomestWei/patent-disclosure-skill) 生成改进方案与中国专利技术交底书，并每日产出技术文章供订阅。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

---

## ✨ 功能特性

### 🔄 LKML 全量同步
- 拉取 [lore.kernel.org](https://lore.kernel.org/linux-kernel/) 月度 mbox 归档（2000 年至今）
- 邮件解析入 PostgreSQL，提取 message_id / subject / author / patch_id / 子系统
- Celery Beat 每日 03:00 增量同步当月 + 上月

### 🏗️ 历史分析 4 阶段流水线（核心）

```
[Stage 1: 候选查找]   →  [Stage 2: 上游对照+分类]  →  [Stage 3: 优化方案]  →  [Stage 4: 专利提取]
   扫描 LKML              本地 kernel git 镜像         调用 OpenCode           调用 patent-disclosure-skill
   过滤性能优化 PATCH      patch-id 匹配合入状态        生成改进方案 .md         产出交底书 .md + .docx
                          按子系统+优化类型分类         ✅ 可重试（版本化）       ✅ 可重试（版本化）
```

- 每个条目独立状态机：`pending / running / success / failed / retrying`
- Stage 3/4 失败可重试，保留历史版本（v1, v2, v3...），不覆盖旧产出
- WebSocket 实时推送阶段进度
- 界面以 4 列卡片+箭头连接展示，每阶段产出列表化

### 📰 每日更新
- 每日 06:00 自动拉取昨日 LKML
- 重要度评分：reply 数 × Maintainer 参与 × PATCH 类型权重
- 按子系统聚类 → LLM 生成单篇技术文章 .md
- 支持手动重新生成指定日期

### ⚙️ OpenCode 配置中心（图形化）
| 配置组 | 字段 |
|---|---|
| 基础 | API Base URL、API Key（AES 加密存储）、模型名、超时、最大 token |
| Skills | 技能仓库列表（git_url + branch + 启用开关），预置 patent-disclosure-skill |
| 提示词 | Stage3 优化 prompt、Stage4 专利 prompt，支持 `{{proposal}}` `{{context}}` 变量 |
| 测试 | "运行测试任务"按钮，验证配置可用性 |

### 📬 订阅系统
- 订阅维度：每日文章 / Stage3 产出 / Stage4 产出 / 指定子系统
- 产出落盘 → 异步发邮件（HTML 摘要 + 链接）
- 退订链接（一次性 token）

### 👥 用户与权限
- 多用户 + RBAC：`admin`（全部）/ `analyst`（分析与配置）/ `viewer`（只读）
- JWT 认证 + 前端路由守卫
- 首次启动自动创建 admin 账号

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│             前端 (React 18 + Vite + TS + AntD 5)              │
│  Login · Dashboard · LKML · History(4阶段流水线) · Daily ·     │
│  OpenCode配置中心 · Subscriptions · Users                      │
└──────────────────────────────────────────────────────────────┘
                              ▲ REST + WebSocket
┌──────────────────────────────────────────────────────────────┐
│         后端 (FastAPI + Python 3.11 + Celery)                 │
│  Auth · LKML · History · Daily · OpenCode · Subscriptions     │
│  Services: lkml_sync · kernel_mirror · pipeline ·             │
│            opencode_runner · daily_digest · notifier          │
└──────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────┐
│            Celery Worker + Beat (定时任务)                     │
│  sync_lkml · fetch_kernel · run_pipeline ·                   │
│  run_stage_item(retry) · daily_digest                        │
└──────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────┐
│  PostgreSQL (元数据) · Redis (broker+进度) · 本地卷             │
│  kernel-mirror · lkml-mbox · outputs · opencode-config        │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 · Vite 6 · TypeScript 5 · Ant Design 5 · Tailwind CSS · Zustand · React Router 7 · React Markdown |
| 后端 | FastAPI 0.115 · Python 3.11 · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · python-jose (JWT) · passlib (bcrypt) · aiohttp |
| 异步任务 | Celery 5.4 · Redis 7 (broker + result backend) · Celery Beat (定时调度) |
| 数据存储 | PostgreSQL 16 · Redis 7 · 本地卷（kernel git 镜像 / lkml mbox / 产出物 / opencode 配置） |
| 部署 | Docker Compose · Nginx（前端静态服务 + API 反代 + WebSocket 升级） |
| 外部依赖 | [lore.kernel.org](https://lore.kernel.org/linux-kernel/) · [git.kernel.org](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git) · [OpenCode CLI](https://github.com/sst/opencode) · [patent-disclosure-skill](https://github.com/handsomestWei/patent-disclosure-skill) |

---

## 🚀 快速开始

### 前置要求
- Docker 20+ 与 Docker Compose v2
- 磁盘空间 ≥ 10GB（kernel git 镜像约 5GB）
- OpenCode 兼容的 LLM API Key（OpenAI / Anthropic / 其他兼容服务）

### 1. 克隆仓库
```bash
git clone https://github.com/yangzhenyu-123/lkml.git
cd lkml
```

### 2. 配置环境变量
```bash
cp .env.example .env
```

编辑 `.env`，**必须修改**以下项：
```bash
POSTGRES_PASSWORD=your_strong_password
JWT_SECRET=your_random_long_string
INIT_ADMIN_PASSWORD=your_admin_password
OPENCODE_API_BASE=https://api.openai.com/v1
OPENCODE_API_KEY=sk-your-actual-api-key
OPENCODE_MODEL=gpt-4o
```

### 3. 启动服务
```bash
docker compose up -d
```

首次启动会：
- 拉取镜像并构建（约 5-10 分钟）
- `kernel-mirror` 容器开始克隆 Linux kernel 仓库（约 5GB，耗时较长）
- `backend` 容器自动运行 Alembic 迁移并创建 admin 账号

### 4. 访问
| 服务 | 地址 | 说明 |
|---|---|---|
| 前端 | http://localhost:8080 | 主界面 |
| 后端 API | http://localhost:8000 | FastAPI |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | 元数据 |
| Redis | localhost:6379 | broker |

使用 `.env` 中配置的 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` 登录。

---

## 📂 项目结构

```
lkml/
├── docker-compose.yml              # 7 服务编排
├── .env.example                    # 环境变量模板
├── kernel-mirror/                  # 本地 kernel git 镜像容器
│   ├── Dockerfile
│   └── init-and-fetch.sh           # clone + 定期 fetch + 优雅退出
├── backend/                        # FastAPI + Celery
│   ├── Dockerfile                  # 含 opencode CLI 安装
│   ├── requirements.txt
│   ├── alembic/                    # 数据库迁移
│   └── app/
│       ├── core/                   # config, security(JWT+AES), deps, ws_manager
│       ├── db/                     # async SQLAlchemy
│       ├── models/                 # 9 张表
│       ├── schemas/                # Pydantic v2
│       ├── api/v1/                 # 7 路由模块 + WebSocket
│       ├── services/               # lkml_sync, kernel_mirror, pipeline,
│       │                           # opencode_runner, daily_digest, notifier
│       └── workers/                # Celery + Beat
├── frontend/                       # React + Vite + TS + AntD
│   ├── Dockerfile                  # 多阶段构建 + nginx
│   ├── nginx.conf                  # SPA + API 反代 + WS 升级
│   └── src/
│       ├── api/                    # axios + 6 业务模块
│       ├── store/                  # Zustand auth
│       ├── hooks/                  # useWebSocket
│       ├── components/             # Layout, History/, OpenCode/
│       ├── pages/                  # 11 个页面
│       └── utils/                  # format
└── volumes/                        # 持久化卷（git ignore 内容）
    ├── kernel-mirror/              # Linux git 镜像
    ├── lkml-mbox/                  # mbox 归档
    ├── outputs/                    # 历史分析产出
    └── opencode-config/            # OpenCode 配置与技能
```

---

## 🎨 设计风格

**Editorial Engineering Dashboard** — 工程化但带杂志感

| 元素 | 规范 |
|---|---|
| 主色 | 墨蓝 `#0B1F3A` |
| 强调色 | 暖橙 `#FF6B35` |
| 背景 | 米白 `#F5F1E8` |
| 阶段色 | Stage1 蓝 / Stage2 紫 / Stage3 琥珀 / Stage4 绿 |
| 标题字体 | [Sora](https://fonts.google.com/specimen/Sora)（几何现代感） |
| 正文字体 | [Inter](https://fonts.google.com/specimen/Inter) |
| 代码字体 | [JetBrains Mono](https://www.jetbrains.com/lp/mono/) |

---

## 🔧 核心数据模型

### Email（LKML 邮件）
```
message_id(PK) · in_reply_to · subject · author · date · body ·
patch_id · refs[] · is_patch · subsystem · raw_mbox_path · reply_count
```

### AnalysisJob / StageRecord / JobItem（4 阶段流水线）
```
AnalysisJob: id · name · year_start · year_end · subsystem_filter ·
             keyword_filter · status · current_stage · created_by
StageRecord:  job_id · stage_no(1-4) · status · total/success/failed_items
JobItem:      job_id · stage_no · parent_item_id · title ·
              email_message_id · patch_id · author · subsystem ·
              optimization_type · merged_upstream · status · version ·
              output_path · log_path · error_message · token_usage
```

### OpenCodeConfig（单例）+ SkillConfig
```
OpenCodeConfig: api_base · api_key_enc(AES) · model · timeout · max_tokens ·
                env_json · prompt_templates{stage3, stage4}
SkillConfig:    name · git_url · local_path · branch · enabled
```

---

## ⏰ 定时任务

| 任务 | Cron | 说明 |
|---|---|---|
| `daily-lkml-sync` | `0 3 * * *` | 每日 03:00 同步当月 + 上月 mbox |
| `daily-digest` | `0 6 * * *` | 每日 06:00 生成昨日技术文章 + 触发订阅邮件 |
| `weekly-kernel-fetch` | `0 4 * * 0` | 每周日 04:00 fetch kernel 镜像最新提交 |

---

## 🌐 API 概览

Base URL: `http://localhost:8000/api/v1`

| 模块 | 端点 |
|---|---|
| 认证 | `POST /auth/login` · `POST /auth/refresh` · `GET /auth/me` |
| LKML | `GET /lkml/emails` · `GET /lkml/search` · `POST /lkml/sync` |
| 历史 | `POST /history/jobs` · `GET /history/jobs/{id}` · `POST /history/jobs/{id}/stages/{n}/items/{iid}/retry` · `WS /history/jobs/{id}/stream` |
| 每日 | `GET /daily/articles` · `GET /daily/articles/{id}` · `POST /daily/regenerate` |
| OpenCode | `GET/PUT /opencode/config` · `GET/POST/DELETE /opencode/skills` · `POST /opencode/test` |
| 订阅 | `GET/POST/DELETE /subscriptions` · `GET /subscriptions/unsubscribe/{token}` |
| 用户 | `GET/POST/PATCH/DELETE /users`（admin only） |

完整 API 文档：http://localhost:8000/docs

---

## 🛠️ 开发

### 后端本地开发
```bash
cd backend
pip install -r requirements.txt
# 启动 PostgreSQL + Redis（可用 docker compose up postgres redis）
alembic upgrade head
uvicorn app.main:app --reload --port 8000
# 另一个终端启动 Celery
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

### 前端本地开发
```bash
cd frontend
npm install
npm run dev      # 启动 Vite 开发服务器 http://localhost:5173
npm run build    # 生产构建
npm run check    # TypeScript 类型检查
```

### 类型检查
```bash
# 前端
cd frontend && npx tsc --noEmit

# 后端
cd backend && python -c "from app.main import app"
```

---

## ✅ 近期完成的修复

下列早期 TODO 已全部解决，现按真实 OpenCode CLI 适配：

1. **`backend/Dockerfile`**：`npm install -g opencode-ai`（官方包名，详见 [opencode.ai/docs](https://opencode.ai/docs)）
2. **`backend/app/services/opencode_runner.py`**：完全重写为 `opencode run "<prompt>" --model provider/model` 形式；技能通过将其 `SKILL.md` 拼到 prompt 前缀激活；多 provider 凭据通过 `env_json` 注入子进程
3. **`backend/app/main.py`**：预置 patent-disclosure-skill 的 `git_url` 已指向实际仓库 `https://github.com/handsomestWei/patent-disclosure-skill`
4. **前端"查看产出"**：后端已实现 `GET /api/v1/history/jobs/{job_id}/items/{item_id}/output?kind=output|log` 端点，含路径穿越防护
5. **`OpenCodeConfig` schema**：`model` 字段明确支持 `provider/model` 格式（如 `openai/gpt-4o`、`anthropic/claude-sonnet-4-5`），`env_json` 用于多 provider 凭据

## ⚠️ 待办事项

- Stage 4 产出的 `.docx` 转换（可选，需要 pandoc 容器扩展）
- OpenCode 子进程 token 用量解析目前依赖输出正则，可考虑使用 `--format json` 改进
- kernel-mirror 首次 clone 全量仓库耗时较长，生产环境建议预挂载卷

---

## 🔒 安全说明

- API Key 使用 Fernet (AES) 对称加密存储于数据库，API 返回 `api_key_set: bool` 不回传明文
- SMTP 凭据同样加密存储
- JWT 鉴权 + RBAC 路由守卫
- `.env` 文件已加入 `.gitignore`，不会提交到仓库
- `node_modules` / `dist` / `__pycache__` / 卷数据均已忽略

---

## 📝 License

MIT License © [yangzhenyu-123](https://github.com/yangzhenyu-123)

---

## 🙏 致谢

- [patent-disclosure-skill](https://github.com/handsomestWei/patent-disclosure-skill) — 中国专利技术交底书生成技能
- [lore.kernel.org](https://lore.kernel.org/) — Linux 内核邮件列表官方归档
- [Linux Kernel Archive](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git) — 上游 kernel 仓库
- [OpenCode](https://github.com/sst/opencode) — AI 编码 CLI
