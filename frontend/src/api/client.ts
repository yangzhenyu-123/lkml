import axios, { AxiosError, AxiosInstance } from "axios";
import { message as antdMessage } from "antd";
import { useAuthStore } from "@/store/authStore";

const baseURL = (import.meta.env.VITE_API_BASE as string) || "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${baseURL}/api/v1`,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截：注入 JWT
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截：401 自动登出 + 错误提示
apiClient.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login") {
        useAuthStore.getState().logout();
        antdMessage.error("登录已过期，请重新登录");
        setTimeout(() => {
          window.location.href = "/login";
        }, 600);
      }
    } else if (error.response?.data?.detail) {
      const detail = error.response.data.detail;
      antdMessage.error(typeof detail === "string" ? detail : "请求失败");
    } else if (error.message) {
      antdMessage.error(error.message);
    }
    return Promise.reject(error);
  }
);

// 构造 WebSocket URL
export function buildWsUrl(path: string): string {
  const wsBase = baseURL.replace(/^http/, "ws");
  const token = useAuthStore.getState().token;
  const sep = path.includes("?") ? "&" : "?";
  return `${wsBase}/api/v1${path}${sep}token=${encodeURIComponent(token || "")}`;
}
