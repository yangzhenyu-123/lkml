// 与后端 schemas 对齐的类型定义

export type UserRole = "admin" | "analyst" | "viewer";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// ============ LKML Email ============
export interface Email {
  message_id: string;
  in_reply_to: string | null;
  subject: string;
  author: string;
  date: string;
  body: string | null;
  patch_id: string | null;
  refs: string[];
  is_patch: boolean;
  subsystem: string | null;
  raw_mbox_path: string | null;
  reply_count: number;
}

export interface EmailListResp {
  total: number;
  items: Email[];
}

export interface SyncRequest {
  year_month?: string; // YYYY-MM
}

export interface SyncResp {
  task_id: string;
  message: string;
}

// ============ 历史分析 ============
export type JobStatus =
  | "pending"
  | "running"
  | "stage1"
  | "stage2"
  | "stage3"
  | "stage4"
  | "completed"
  | "failed";

export type ItemStatus = "pending" | "running" | "success" | "failed" | "retrying";

export interface AnalysisJob {
  id: number;
  name: string;
  year_start: number;
  year_end: number;
  subsystem_filter: string | null;
  keyword_filter: string | null;
  status: JobStatus;
  current_stage: number;
  created_by: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface AnalysisJobCreate {
  name: string;
  year_start: number;
  year_end: number;
  subsystem_filter?: string;
  keyword_filter?: string;
}

export interface StageRecord {
  id: number;
  job_id: number;
  stage_no: 1 | 2 | 3 | 4;
  status: "pending" | "running" | "completed" | "failed";
  total_items: number;
  success_items: number;
  failed_items: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobItem {
  id: number;
  job_id: number;
  stage_no: 1 | 2 | 3 | 4;
  parent_item_id: number | null;
  title: string | null;
  email_message_id: string | null;
  patch_id: string | null;
  author: string | null;
  subsystem: string | null;
  optimization_type: string | null;
  merged_upstream: boolean | null;
  status: ItemStatus;
  version: number;
  output_path: string | null;
  log_path: string | null;
  error_message: string | null;
  token_usage: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface JobDetail {
  job: AnalysisJob;
  stages: StageRecord[];
  items: JobItem[];
}

// WebSocket 事件
export interface WsJobUpdate {
  event: "job_update";
  job_id: number;
  status: JobStatus;
  current_stage: number;
}
export interface WsStageUpdate {
  event: "stage_update";
  job_id: number;
  stage_no: number;
  status: "pending" | "running" | "completed" | "failed";
  success_items: number;
  failed_items: number;
  total_items: number;
}
export interface WsItemUpdate {
  event: "item_update";
  job_id: number;
  stage_no: number;
  item_id: number;
  status: ItemStatus;
  version: number;
  output_path: string | null;
  error_message: string | null;
  token_usage: number;
}
export type WsEvent = WsJobUpdate | WsStageUpdate | WsItemUpdate;

// ============ 每日文章 ============
export interface DailyArticle {
  id: number;
  date: string;
  title: string;
  summary: string;
  content_path: string | null;
  subsystems: string[];
  email_ids: string[];
  created_at: string;
}

export interface ArticleListResp {
  total: number;
  items: DailyArticle[];
}

// ============ OpenCode ============
export interface OpenCodeConfig {
  id: number;
  api_base: string;
  api_key_set: boolean; // 不回传明文
  model: string;
  timeout: number;
  max_tokens: number;
  env_json: Record<string, string>;
  prompt_templates: {
    stage3: string;
    stage4: string;
  };
}

export interface OpenCodeConfigUpdate {
  api_base?: string;
  api_key?: string; // 仅在更新时传
  model?: string;
  timeout?: number;
  max_tokens?: number;
  env_json?: Record<string, string>;
  prompt_templates?: {
    stage3: string;
    stage4: string;
  };
}

export interface SkillConfig {
  id: number;
  name: string;
  git_url: string;
  local_path: string;
  branch: string;
  enabled: boolean;
}

export interface SkillConfigCreate {
  name: string;
  git_url: string;
  branch?: string;
  local_path?: string;
  enabled?: boolean;
}

export interface OpenCodeTestRequest {
  prompt?: string;
}

export interface OpenCodeTestResult {
  success: boolean;
  output: string;
  duration_ms: number;
  error?: string;
}

// ============ 订阅 ============
export type SubscriptionType = "daily_article" | "stage3_output" | "stage4_output" | "subsystem";

export interface Subscription {
  id: number;
  user_id: number;
  type: SubscriptionType;
  subsystem_filter: string | null;
  email_notify: boolean;
  unsubscribe_token: string;
  created_at: string;
}

export interface SubscriptionCreate {
  type: SubscriptionType;
  subsystem_filter?: string;
  email_notify?: boolean;
}

// ============ 通用 ============
export interface PaginatedResp<T> {
  total: number;
  items: T[];
}

export interface ApiError {
  detail: string;
}
