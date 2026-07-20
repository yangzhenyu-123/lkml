import { apiClient } from "./client";

export interface DashboardStats {
  email_count: number;
  job_count: number;
  article_count: number;
  retry_pending: number;
}

export const statsApi = {
  dashboard: () =>
    apiClient.get<DashboardStats>("/stats/dashboard").then((r) => r.data),
};
