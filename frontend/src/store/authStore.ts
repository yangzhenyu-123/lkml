import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, UserRole } from "@/types";
import { apiClient } from "@/api/client";

export interface LoginResult {
  ok: boolean;
  error?: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      login: async (username, password) => {
        try {
          const formData = new URLSearchParams();
          formData.append("username", username);
          formData.append("password", password);
          const resp = await apiClient.post("/auth/login", formData, {
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
          });
          const { access_token } = resp.data;
          if (!access_token) {
            return { ok: false, error: "登录响应异常：未返回 access_token" };
          }
          set({ token: access_token });
          try {
            await get().fetchMe();
          } catch (e) {
            // fetchMe 失败说明 token 无效或 /auth/me 不可达
            set({ token: null, user: null });
            const msg = e instanceof Error ? e.message : String(e);
            return {
              ok: false,
              error: `登录成功但获取用户信息失败（token 可能无效）：${msg}`,
            };
          }
          return { ok: true };
        } catch (e: any) {
          // 详细错误，便于诊断
          if (e?.response?.status === 401) {
            return { ok: false, error: "用户名或密码错误" };
          }
          if (e?.response?.status === 422) {
            return { ok: false, error: "请求格式错误（422），请联系管理员检查后端版本" };
          }
          if (e?.code === "ERR_NETWORK") {
            return {
              ok: false,
              error: `网络错误：无法连接 API（${e.message}）。请检查前端是否使用了错误的 API 地址，或 nginx 反代是否正常`,
            };
          }
          const detail = e?.response?.data?.detail;
          if (detail) {
            return { ok: false, error: typeof detail === "string" ? detail : JSON.stringify(detail) };
          }
          return { ok: false, error: e?.message || "登录失败（未知错误）" };
        }
      },
      logout: () => set({ token: null, user: null }),
      fetchMe: async () => {
        try {
          const resp = await apiClient.get<User>("/auth/me");
          set({ user: resp.data });
        } catch (e) {
          set({ token: null, user: null });
          throw e;
        }
      },
      hasRole: (...roles) => {
        const u = get().user;
        if (!u) return false;
        if (u.role === "admin") return true; // admin 拥有全部
        return roles.includes(u.role);
      },
    }),
    {
      name: "lkml-auth",
      partialize: (state) => ({ token: state.token }), // 仅持久化 token
    }
  )
);
