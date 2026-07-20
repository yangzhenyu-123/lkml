import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spin } from "antd";
import { useAuthStore } from "@/store/authStore";
import MainLayout from "@/components/Layout/MainLayout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import LkmlList from "@/pages/LkmlList";
import LkmlDetail from "@/pages/LkmlDetail";
import HistoryList from "@/pages/HistoryList";
import HistoryDetail from "@/pages/HistoryDetail";
import DailyList from "@/pages/DailyList";
import DailyDetail from "@/pages/DailyDetail";
import OpenCodeConfig from "@/pages/OpenCodeConfig";
import Subscriptions from "@/pages/Subscriptions";
import Users from "@/pages/Users";

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
