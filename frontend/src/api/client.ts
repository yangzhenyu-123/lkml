import axios, { AxiosError, AxiosInstance } from "axios";
import { message as antdMessage } from "antd";
import { useAuthStore } from "@/store/authStore";

// baseURL 默认空字符串（同源相对路径），由 nginx 反代 /api/ 到后端。
// 这样无论用户从 localhost、内网 IP 还是域名访问前端，API 调用都走同源，
// 避免跨域与硬编码 localhost 导致从其他主机访问时 API 失效。
// 仅在前后端分离部署（前端独立域名）时才需通过 VITE_API_BASE 指定后端地址。
const baseURL = (import.meta.env.VITE_API_BASE as string) || "";

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
// 默认同源（由 nginx 反代 /api/ 到后端），自动使用当前页面的 ws 协议与 host
export function buildWsUrl(path: string): string {
  const token = useAuthStore.getState().token;
  const sep = path.includes("?") ? "&" : "?";
  if (baseURL) {
    // 显式指定后端地址（前后端分离部署）
    const wsBase = baseURL.replace(/^http/, "ws");
    return `${wsBase}/api/v1${path}${sep}token=${encodeURIComponent(token || "")}`;
  }
  // 同源：基于当前页面协议与 host 构造 ws URL
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1${path}${sep}token=${encodeURIComponent(token || "")}`;
}
