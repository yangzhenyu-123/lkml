# LKML 性能优化专利挖掘平台 - PRD

## 1. 产品概述

### 1.1 产品定位
面向内核研发与专利工程师的 LKML（Linux Kernel Mailing List）自动化分析平台。自动同步 LKML 全量邮件，长期跟踪性能优化类提案，对照上游 kernel 仓库识别未合入的优化方案，借助 OpenCode + patent-disclosure-skill 生成改进方案与中国专利技术交底书，并每日产出技术文章供订阅。

### 1.2 核心价值
- **未合入提案挖掘**：自动找出 LKML 历史中性能优化但未被主线合入的提案
- **专利闭环**：基于未合入提案，结合 OpenCode 与 patent-disclosure-skill 自动产出技术交底书
- **每日情报**：每日自动总结 LKML 重要邮件为技术文章，邮件订阅推送
- **图形化配置**：全程可视化配置 OpenCode、技能、提示词，无需编辑配置文件

### 1.3 目标用户与角色
| 角色 | 权限 |
|---|---|
| admin | 全部权限，含用户管理、OpenCode 配置 |
| analyst | 创建/重试分析任务、查看产出、配置 OpenCode |
| viewer | 只读浏览邮件、文章、产出 |

## 2. 功能需求

### 2.1 LKML 同步
- 全量同步 lore.kernel.org/linux-kernel 月度 mbox 归档（2000 年至今）
- 增量同步：每日 03:00 拉取当月 + 上月
- 邮件解析入 PostgreSQL：message_id / subject / author / date / body / patch_id / 子系统识别
- 浏览与全文检索

### 2.2 历史分析 4 阶段流水线（核心）

| 阶段 | 输入 | 处理 | 产出 | 可重试 |
|---|---|---|---|---|
| ① 候选查找 | 时间窗、子系统、关键词 | 扫描 LKML，过滤性能优化类 PATCH 邮件 | proposals 列表 | 否 |
| ② 上游对照+分类 | proposals | 本地 kernel git 镜像 patch-id 匹配，标记 merged/unmerged，按子系统+优化类型分类 | unmerged_proposals 列表 | 否 |
| ③ 优化方案 | 单条未合入提案 | 调 OpenCode 注入技能上下文生成改进方案 | optimization_proposals (.md) | **是** |
| ④ 专利提取 | 优化方案 | 调 OpenCode + patent-disclosure-skill 产出交底书 | patent_disclosures (.md + .docx) | **是** |

- 每个条目独立状态机：pending / running / success / failed / retrying
- 重试创建新版本（v1, v2, v3...），保留历史
- WebSocket 实时推送阶段进度
- 界面以"4 列卡片+列表"形式展示每阶段产出

### 2.3 每日更新
- 每日 06:00 拉取昨日 LKML
- 重要度评分：reply 数 × Maintainer 参与 × PATCH 类型权重
- 按子系统聚类 → LLM 生成单篇技术文章 .md
- 支持手动重新生成指定日期

### 2.4 OpenCode 配置中心（图形化）
| 配置组 | 字段 |
|---|---|
| 基础 | API Base URL、API Key（AES 加密）、模型名、超时、最大 token |
| Skills | 技能仓库列表（git_url + local_path + branch + enabled），预置 patent-disclosure-skill |
| 提示词模板 | Stage3 优化 prompt、Stage4 专利 prompt，支持 `{{proposal}}` `{{context}}` 变量 |
| 子进程 | 工作目录、环境变量、超时、最大重试次数 |
| 测试 | "运行测试任务"按钮，验证配置可用性 |

### 2.5 订阅系统
- 订阅维度：每日文章 / 历史分析 Stage3 产出 / Stage4 产出 / 指定子系统
- 产出落盘 → 异步发邮件（HTML 摘要 + 链接）
- 退订链接（一次性 token）

### 2.6 用户与权限
- 多用户 + RBAC（admin / analyst / viewer）
- JWT 认证 + 路由守卫
- 首次启动自动创建 admin 账号

## 3. 非功能需求
- **部署**：Docker Compose 一键部署
- **性能**：单机支撑百万级邮件元数据检索
- **可用性**：服务异常自动重启，Celery 任务可重试
- **安全**：API Key 加密存储、JWT 鉴权、SMTP 凭据加密

## 4. 技术选型
- 前端：React 18 + Vite + TypeScript + Ant Design 5
- 后端：FastAPI + Python 3.11 + Celery + WebSocket
- 存储：PostgreSQL 16 + Redis 7
- 部署：Docker Compose（frontend / backend / worker / beat / postgres / redis / kernel-mirror）

## 5. 页面清单
1. **登录页**
2. **Dashboard** - 总览：同步状态、近期任务、每日文章、订阅
3. **LKML 邮件浏览** - 列表/详情/检索/手动同步
4. **历史分析** - 任务列表 + 4 阶段流水线详情（含重试按钮、产出预览、版本对比）
5. **每日文章** - 列表/详情/重新生成
6. **OpenCode 配置中心** - 基础配置/Skills 管理/提示词模板/测试
7. **订阅管理** - 我的订阅/新增/删除
8. **用户管理**（admin） - CRUD
