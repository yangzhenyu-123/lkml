import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, UserRole } from "@/types";
import { apiClient } from "@/api/client";

interface AuthState {
  token: string | null;
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
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
          set({ token: access_token });
          await get().fetchMe();
          return true;
        } catch {
          return false;
        }
      },
      logout: () => set({ token: null, user: null }),
      fetchMe: async () => {
        try {
          const resp = await apiClient.get<User>("/auth/me");
          set({ user: resp.data });
        } catch {
          set({ token: null, user: null });
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
