# LKML 性能优化专利挖掘平台 - 技术架构文档

## 1. 总体架构

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

## 2. 后端 API 契约（已实现）

Base URL: `http://localhost:18000/api/v1`

### 认证
- `POST /auth/login` → `{access_token, token_type}`
- `POST /auth/refresh`
- `GET /auth/me`

### LKML 邮件
- `GET /lkml/emails?skip=&limit=&start_date=&end_date=&subsystem=&is_patch=&q=`
- `GET /lkml/search?q=`
- `POST /lkml/sync` body `{year_month?}` → `{task_id}`

### 历史分析
- `POST /history/jobs` body `{name, year_start, year_end, subsystem_filter?, keyword_filter?}` → `AnalysisJob`
- `GET /history/jobs?skip=&limit=&status=`
- `GET /history/jobs/{id}` → `{job, stages:[], items:[]}`
- `POST /history/jobs/{id}/stages/{n}/items/{iid}/retry` → 新版本 JobItem
- `WS /history/jobs/{id}/stream` → 推送 `job_update` / `stage_update` / `item_update`

### 每日文章
- `GET /daily/articles?skip=&limit=&date_from=&date_to=`
- `GET /daily/articles/{id}`
- `POST /daily/regenerate` body `{date?}`

### OpenCode 配置
- `GET /opencode/config`
- `PUT /opencode/config`
- `GET /opencode/skills`
- `POST /opencode/skills` body `{name, git_url, branch?, local_path?}`
- `DELETE /opencode/skills/{id}`
- `POST /opencode/test` body `{prompt?}` → `{success, output, duration_ms}`

### 订阅
- `GET /subscriptions`
- `POST /subscriptions` body `{type, subsystem_filter?, email_notify?}`
- `DELETE /subscriptions/{id}`
- `GET /subscriptions/unsubscribe/{token}`

### 用户（admin）
- `GET /users` · `POST /users` · `PATCH /users/{id}` · `DELETE /users/{id}`

## 3. 数据模型关键字段

### Email
```
message_id(PK) · in_reply_to · subject · author · date · body ·
patch_id · refs[] · is_patch · subsystem · raw_mbox_path · reply_count
```

### AnalysisJob / StageRecord / JobItem
```
AnalysisJob: id · name · year_start · year_end · subsystem_filter ·
             keyword_filter · status · current_stage · created_by
StageRecord:  job_id · stage_no(1-4) · status · total/success/failed_items
JobItem:      job_id · stage_no · parent_item_id · title ·
              email_message_id · patch_id · author · subsystem ·
              optimization_type · merged_upstream · status · version ·
              output_path · log_path · error_message · token_usage
```

### OpenCodeConfig（单例 id=1）+ SkillConfig
```
OpenCodeConfig: api_base · api_key_enc · model · timeout · max_tokens ·
                env_json · prompt_templates{stage3, stage4}
SkillConfig:    name · git_url · local_path · branch · enabled
```

## 4. 4 阶段流水线状态机

```
[Job: pending]
   ↓ 触发 run_pipeline_task
[Stage 1: 候选查找]  → 创建 JobItem(stage_no=1) 列表
   ↓ Stage1 全部 success
[Stage 2: 上游对照+分类]
   - 对每个 Stage1 item: kernel_mirror.check_merged(patch_id)
   - merged_upstream=True 标记 success（不入下一阶段）
   - merged_upstream=False 创建 JobItem(stage_no=2)
   ↓ Stage2 全部 success
[Stage 3: 优化方案（可重试）]
   - 对每个 Stage2 item: opencode_runner.run_optimization(...)
   - 产出 OUTPUTS_PATH/{job}/stage3/{item}_v{version}.md
   ↓ Stage3 全部 success（失败可单独 retry，创建新 version）
[Stage 4: 专利提取（可重试）]
   - 对每个 Stage3 success item: opencode_runner.run_patent_disclosure(...)
   - 产出 .md + .docx
   ↓
[Job: completed]
```

## 5. WebSocket 事件
```json
{"event": "job_update", "job_id": 1, "status": "stage3", "current_stage": 3}
{"event": "stage_update", "job_id": 1, "stage_no": 3, "status": "running", "success_items": 2}
{"event": "item_update", "job_id": 1, "stage_no": 3, "item_id": 5, "status": "success", "version": 1, "output_path": "..."}
```

## 6. 前端技术栈与结构

### 技术栈
- React 18 + Vite 5 + TypeScript 5
- Ant Design 5（组件库）
- React Router 6（路由 + 守卫）
- Zustand（状态管理）
- Axios（HTTP）
- Dayjs（时间）
- @ant-design/icons
- React Markdown + rehype-highlight（产出预览）

### 设计风格
**"Editorial Engineering Dashboard"** - 工程化但带杂志感
- 主色：深邃墨蓝 (#0B1F3A) + 暖橙强调 (#FF6B35) + 米白底 (#F5F1E8)
- 字体：标题用 `Sora`（几何现代感），正文用 `Inter` 紧凑变体；代码 `JetBrains Mono`
- 布局：左侧固定侧栏（深墨蓝）+ 顶部细 header + 主内容区
- 卡片：略带阴影 + 圆角 8px + 1px 边框
- 4 阶段流水线视图：横向 4 列卡片，每列独立滚动，卡片间用箭头连接，状态用色彩+图标区分

### 目录结构
```
frontend/
├── Dockerfile          # 多阶段构建，nginx 服务
├── nginx.conf
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── .env.example
└── src/
    ├── main.tsx
    ├── App.tsx                  # 路由 + 守卫
    ├── api/                     # axios 实例 + 各模块 API
    │   ├── client.ts
    │   ├── auth.ts
    │   ├── lkml.ts
    │   ├── history.ts
    │   ├── daily.ts
    │   ├── opencode.ts
    │   ├── subscriptions.ts
    │   └── users.ts
    ├── store/                   # Zustand
    │   ├── authStore.ts
    │   └── wsStore.ts
    ├── components/
    │   ├── Layout/              # MainLayout, Sidebar, Header
    │   ├── PipelineView/        # 4 阶段流水线核心组件
    │   ├── StageCard/
    │   ├── ItemCard.tsx
    │   ├── RetryButton.tsx
    │   ├── OutputViewer.tsx     # Markdown/docx 预览
    │   ├── StatusBadge.tsx
    │   └── EmptyState.tsx
    ├── pages/
    │   ├── Login.tsx
    │   ├── Dashboard.tsx
    │   ├── LkmlList.tsx
    │   ├── LkmlDetail.tsx
    │   ├── HistoryList.tsx
    │   ├── HistoryDetail.tsx   # 4 阶段流水线详情
    │   ├── DailyList.tsx
    │   ├── DailyDetail.tsx
    │   ├── OpenCodeConfig.tsx
    │   ├── Subscriptions.tsx
    │   └── Users.tsx
    ├── hooks/
    │   ├── useWebSocket.ts
    │   └── useAuth.ts
    ├── types/                   # TS 类型定义（对齐后端 schema）
    │   └── index.ts
    └── utils/
        ├── request.ts
        └── format.ts
```

## 7. 关键页面交互设计

### HistoryDetail（核心页）
- 顶部：任务名 + 状态徽章 + 时间范围 + 子系统筛选 + 重试按钮
- 主体：4 列网格布局
  ```
  ┌─Stage1─┐ → ┌─Stage2─┐ → ┌─Stage3─┐ → ┌─Stage4─┐
  │ 候选列表 │   │ 未合入   │   │ 优化方案  │   │ 专利交底 │
  │ 12 项    │   │ 8 项     │   │ 5/8 成功  │   │ 4/5 成功 │
  └─────────┘   └─────────┘   └─────────┘   └─────────┘
  ```
- 每列：标题 + 进度条 + 卡片列表（卡片含状态徽章、作者、子系统、版本号、重试按钮）
- 点击卡片：右侧抽屉展示详情（含 Markdown 渲染、历史版本对比、token 用量、日志）
- 失败卡片：红色边框 + 错误信息 + 显眼重试按钮
- WebSocket 连接：实时更新卡片状态

### OpenCodeConfig
- Tab 布局：基础配置 / Skills / 提示词 / 测试
- Skills 管理：表格 + 新增弹窗 + 启用开关 + 编辑/删除
- 测试：输入框 + "运行测试"按钮 + 实时输出区

### Dashboard
- 4 个统计卡：邮件总数 / 历史任务数 / 今日文章 / 待处理重试
- 2 个图表：最近 7 天同步量、各阶段成功率
- 最近任务列表 + 最近文章列表

## 8. 部署
- Docker Compose 一键起 frontend(18088) / backend(18000) / worker / beat / postgres(35432) / redis(16379) / kernel-mirror
- 前端构建：Vite build → nginx 静态服务 + 反代 /api 到 backend
- 环境变量统一在 .env
