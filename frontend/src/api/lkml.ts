import { apiClient } from "./client";
import type { Email, EmailListResp, SyncRequest, SyncResp } from "@/types";

export const lkmlApi = {
  list: (params: {
    skip?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    subsystem?: string;
    is_patch?: boolean;
    q?: string;
  }) => apiClient.get<EmailListResp>("/lkml/emails", { params }).then((r) => r.data),

  detail: (messageId: string) =>
    apiClient.get<Email>(`/lkml/emails/${encodeURIComponent(messageId)}`).then((r) => r.data),

  search: (q: string, limit = 50) =>
    apiClient.get<{ items: Email[] }>("/lkml/search", { params: { q, limit } }).then((r) => r.data),

  sync: (data: SyncRequest) => apiClient.post<SyncResp>("/lkml/sync", data).then((r) => r.data),
};
