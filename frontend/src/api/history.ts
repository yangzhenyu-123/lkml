import { apiClient } from "./client";
import type {
  AnalysisJob,
  AnalysisJobCreate,
  JobDetail,
  JobItem,
} from "@/types";

export const historyApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) =>
    apiClient.get<{ total: number; items: AnalysisJob[] }>("/history/jobs", { params }).then((r) => r.data),

  detail: (id: number) => apiClient.get<JobDetail>(`/history/jobs/${id}`).then((r) => r.data),

  create: (data: AnalysisJobCreate) =>
    apiClient.post<AnalysisJob>("/history/jobs", data).then((r) => r.data),

  retryItem: (jobId: number, stageNo: number, itemId: number) =>
    apiClient
      .post<JobItem>(`/history/jobs/${jobId}/stages/${stageNo}/items/${itemId}/retry`)
      .then((r) => r.data),

  remove: (id: number) => apiClient.delete(`/history/jobs/${id}`).then((r) => r.data),
};
