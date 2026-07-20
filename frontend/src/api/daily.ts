import { apiClient } from "./client";
import type { DailyArticle, ArticleListResp } from "@/types";

export const dailyApi = {
  list: (params?: { skip?: number; limit?: number; date_from?: string; date_to?: string }) =>
    apiClient.get<ArticleListResp>("/daily/articles", { params }).then((r) => r.data),

  detail: (id: number) =>
    apiClient.get<DailyArticle>(`/daily/articles/${id}`).then((r) => r.data),

  content: (id: number) =>
    apiClient.get<string>(`/daily/articles/${id}/content`, { responseType: "text" }).then((r) => r.data),

  regenerate: (date?: string) =>
    apiClient.post<DailyArticle>("/daily/regenerate", { date }).then((r) => r.data),
};
