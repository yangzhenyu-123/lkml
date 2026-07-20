import { apiClient } from "./client";
import type {
  OpenCodeConfig,
  OpenCodeConfigUpdate,
  SkillConfig,
  SkillConfigCreate,
  OpenCodeTestRequest,
  OpenCodeTestResult,
} from "@/types";

export const opencodeApi = {
  getConfig: () => apiClient.get<OpenCodeConfig>("/opencode/config").then((r) => r.data),
  updateConfig: (data: OpenCodeConfigUpdate) =>
    apiClient.put<OpenCodeConfig>("/opencode/config", data).then((r) => r.data),

  listSkills: () =>
    apiClient.get<{ items: SkillConfig[] }>("/opencode/skills").then((r) => r.data),
  createSkill: (data: SkillConfigCreate) =>
    apiClient.post<SkillConfig>("/opencode/skills", data).then((r) => r.data),
  removeSkill: (id: number) =>
    apiClient.delete(`/opencode/skills/${id}`).then((r) => r.data),

  test: (data: OpenCodeTestRequest) =>
    apiClient.post<OpenCodeTestResult>("/opencode/test", data, { timeout: 300_000 }).then((r) => r.data),
};
