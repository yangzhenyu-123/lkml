import { apiClient } from "./client";
import type { User, UserRole } from "@/types";

export const usersApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<{ total: number; items: User[] }>("/users", { params }).then((r) => r.data),
  create: (data: { username: string; email: string; password: string; role: UserRole }) =>
    apiClient.post<User>("/users", data).then((r) => r.data),
  update: (id: number, data: Partial<{ email: string; password: string; role: UserRole; is_active: boolean }>) =>
    apiClient.patch<User>(`/users/${id}`, data).then((r) => r.data),
  remove: (id: number) => apiClient.delete(`/users/${id}`).then((r) => r.data),
};
