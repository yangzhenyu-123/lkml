import { lazy, Suspense, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spin } from "antd";
import { useAuthStore } from "@/store/authStore";
import MainLayout from "@/components/Layout/MainLayout";
import Login from "@/pages/Login";

// 路由级懒加载：首屏只需加载 Dashboard，其他页面按需加载
// 配合 vite.config.ts 的 manualChunks，第三方库分块缓存，二次访问极快
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const LkmlList = lazy(() => import("@/pages/LkmlList"));
const LkmlDetail = lazy(() => import("@/pages/LkmlDetail"));
const HistoryList = lazy(() => import("@/pages/HistoryList"));
const HistoryDetail = lazy(() => import("@/pages/HistoryDetail"));
const DailyList = lazy(() => import("@/pages/DailyList"));
const DailyDetail = lazy(() => import("@/pages/DailyDetail"));
const OpenCodeConfig = lazy(() => import("@/pages/OpenCodeConfig"));
const Subscriptions = lazy(() => import("@/pages/Subscriptions"));
const Users = lazy(() => import("@/pages/Users"));

function PageLoading() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spin size="large" />
    </div>
  );
}

function RequireAuth({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { token, user, hasRole } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (roles && user && !hasRole(...(roles as never[]))) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function AuthedApp() {
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const user = useAuthStore((s) => s.user);
  useEffect(() => {
    if (!user) fetchMe();
  }, [fetchMe, user]);

  if (!user) {
    return (
      <div className="flex items-center justify-center h-screen bg-paper">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <MainLayout>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lkml" element={<LkmlList />} />
          <Route path="/lkml/:messageId" element={<LkmlDetail />} />
          <Route path="/history" element={<HistoryList />} />
          <Route path="/history/:id" element={<HistoryDetail />} />
          <Route path="/daily" element={<DailyList />} />
          <Route path="/daily/:id" element={<DailyDetail />} />
          <Route
            path="/opencode"
            element={
              <RequireAuth roles={["admin", "analyst"]}>
                <OpenCodeConfig />
              </RequireAuth>
            }
          />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route
            path="/users"
            element={
              <RequireAuth roles={["admin"]}>
                <Users />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </MainLayout>
  );
}

export default function App() {
  const token = useAuthStore((s) => s.token);
  return (
    <Routes>
      {!token ? (
        <>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </>
      ) : (
        <>
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/*" element={<AuthedApp />} />
        </>
      )}
    </Routes>
  );
}
