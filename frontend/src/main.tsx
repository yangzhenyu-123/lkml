import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntdApp, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "./index.css";

// AntD 主题：墨蓝主色 + 暖橙点缀，圆角 8px
const antdTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: "#0B1F3A",
    colorInfo: "#0B1F3A",
    colorLink: "#FF6B35",
    colorLinkHover: "#E5532A",
    colorSuccess: "#10B981",
    colorWarning: "#F59E0B",
    colorError: "#EF4444",
    colorTextBase: "#0B1F3A",
    colorBgLayout: "#F5F1E8",
    colorBgContainer: "#FFFFFF",
    borderRadius: 8,
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    fontSize: 14,
    controlHeight: 36,
  },
  components: {
    Layout: {
      siderBg: "#0B1F3A",
      headerBg: "#FFFFFF",
      headerHeight: 56,
      bodyBg: "#F5F1E8",
    },
    Menu: {
      darkItemBg: "#0B1F3A",
      darkItemSelectedBg: "rgba(255, 107, 53, 0.18)",
      darkItemColor: "rgba(238, 242, 248, 0.75)",
      darkItemHoverColor: "#FFFFFF",
      darkItemSelectedColor: "#FFFFFF",
    },
    Card: {
      borderRadiusLG: 10,
      boxShadowTertiary: "0 1px 3px rgba(11, 31, 58, 0.06)",
    },
    Table: {
      headerBg: "#EEF2F8",
      headerColor: "#0B1F3A",
      borderColor: "#DDE5F0",
      rowHoverBg: "#F5F1E8",
    },
    Button: {
      primaryShadow: "none",
      defaultBorderColor: "#DDE5F0",
    },
  },
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>
);
