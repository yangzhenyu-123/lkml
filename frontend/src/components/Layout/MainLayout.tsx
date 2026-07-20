import { useMemo } from "react";
import { Layout, Avatar, Dropdown, Button, Tooltip } from "antd";
import {
  DashboardOutlined,
  MailOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  ToolOutlined,
  BellOutlined,
  TeamOutlined,
  LogoutOutlined,
  UserOutlined,
  GithubOutlined,
} from "@ant-design/icons";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import type { UserRole } from "@/types";

const { Sider, Header, Content } = Layout;

interface NavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  to: string;
  roles?: UserRole[];
}

const navItems: NavItem[] = [
  { key: "dashboard", label: "总览", icon: <DashboardOutlined />, to: "/" },
  { key: "lkml", label: "LKML 邮件", icon: <MailOutlined />, to: "/lkml" },
  { key: "history", label: "历史分析", icon: <ApartmentOutlined />, to: "/history" },
  { key: "daily", label: "每日文章", icon: <FileTextOutlined />, to: "/daily" },
  { key: "opencode", label: "OpenCode 配置", icon: <ToolOutlined />, to: "/opencode", roles: ["admin", "analyst"] },
  { key: "subscriptions", label: "我的订阅", icon: <BellOutlined />, to: "/subscriptions" },
  { key: "users", label: "用户管理", icon: <TeamOutlined />, to: "/users", roles: ["admin"] },
];

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasRole } = useAuthStore();

  const visibleNav = useMemo(
    () => navItems.filter((it) => !it.roles || hasRole(...(it.roles as never[]))),
    [hasRole]
  );

  const currentKey = useMemo(() => {
    const path = location.pathname;
    if (path === "/") return "dashboard";
    const match = navItems.find((it) => it.to !== "/" && path.startsWith(it.to));
    return match?.key || "dashboard";
  }, [location.pathname]);

  const userMenu = {
    items: [
      {
        key: "logout",
        label: "退出登录",
        icon: <LogoutOutlined />,
      },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === "logout") {
        logout();
        navigate("/login");
      }
    },
  };

  return (
    <Layout className="h-screen">
      <Sider width={232} className="!bg-ink-900 !flex flex-col">
        {/* Logo */}
        <div className="h-14 flex items-center px-5 border-b border-white/5">
          <div className="w-8 h-8 rounded-md bg-ember-500 flex items-center justify-center text-white font-bold font-display">
            L
          </div>
          <div className="ml-3 text-white">
            <div className="font-display font-semibold text-sm leading-tight">LKML Patent</div>
            <div className="text-[10px] text-ink-300 leading-tight">性能优化专利挖掘</div>
          </div>
        </div>

        {/* 导航 */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {visibleNav.map((it) => (
            <Link
              key={it.key}
              to={it.to}
              className={`lk-nav-item ${currentKey === it.key ? "active" : ""}`}
            >
              <span className="text-base">{it.icon}</span>
              <span>{it.label}</span>
            </Link>
          ))}
        </nav>

        {/* 底部 */}
        <div className="px-5 py-3 border-t border-white/5">
          <a
            href="https://github.com/handsomestWei/patent-disclosure-skill"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-xs text-ink-300 hover:text-white transition-colors"
          >
            <GithubOutlined />
            patent-disclosure-skill
          </a>
        </div>
      </Sider>

      <Layout>
        <Header className="!bg-white border-b border-ink-100 flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-display font-semibold text-ink-900 m-0">
              {navItems.find((it) => it.key === currentKey)?.label || "总览"}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Tooltip title="刷新用户信息">
              <Button
                type="text"
                size="small"
                onClick={() => useAuthStore.getState().fetchMe()}
              >
                {user?.username}
              </Button>
            </Tooltip>
            <Dropdown menu={userMenu} placement="bottomRight">
              <div className="flex items-center gap-2 cursor-pointer">
                <Avatar
                  size={32}
                  icon={<UserOutlined />}
                  style={{ backgroundColor: "#0B1F3A" }}
                />
                <div className="hidden md:block text-xs">
                  <div className="font-medium text-ink-900">{user?.email}</div>
                  <div className="text-ink-400 uppercase">{user?.role}</div>
                </div>
              </div>
            </Dropdown>
          </div>
        </Header>

        <Content className="!bg-paper overflow-y-auto">
          <div className="p-6 min-h-full">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
