import { useState } from "react";
import { Card, Input, Button, Form, App } from "antd";
import { UserOutlined, LockOutlined, MailOutlined } from "@ant-design/icons";
import { useAuthStore } from "@/store/authStore";

export default function Login() {
  const { message } = App.useApp();
  const login = useAuthStore((s) => s.login);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true);
    const result = await login(values.username, values.password);
    setLoading(false);
    if (result.ok) {
      message.success("登录成功");
    } else {
      message.error(result.error || "登录失败");
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        background:
          "radial-gradient(circle at 20% 30%, #13294F 0%, #0B1F3A 50%, #08172B 100%)",
      }}
    >
      {/* 背景装饰：网格 + 暖橙光晕 */}
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,107,53,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,107,53,0.06) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      <div
        className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: "#FF6B35" }}
      />

      <div className="relative z-10 w-full max-w-5xl grid md:grid-cols-2 gap-8 items-center">
        {/* 左：品牌介绍 */}
        <div className="hidden md:block text-white">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-lg bg-ember-500 flex items-center justify-center text-white font-bold font-display text-2xl">
              L
            </div>
            <div>
              <div className="font-display font-bold text-xl">LKML Patent</div>
              <div className="text-ink-300 text-sm">性能优化专利挖掘平台</div>
            </div>
          </div>
          <h1 className="font-display text-4xl font-bold leading-tight mb-4">
            从内核邮件列表
            <br />
            <span className="text-ember-500">到中国专利交底书</span>
          </h1>
          <p className="text-ink-200 text-base leading-relaxed mb-8">
            自动同步 LKML 全量归档，识别未合入的性能优化提案，
            借助 OpenCode 与 patent-disclosure-skill 生成改进方案与可交付的技术交底书。
          </p>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "4 阶段流水线", desc: "候选→对照→优化→专利" },
              { label: "全量历史", desc: "2000+ 年至今" },
              { label: "WebSocket 实时", desc: "进度推送" },
              { label: "图形化配置", desc: "OpenCode & Skills" },
            ].map((f) => (
              <div key={f.label} className="border-l-2 border-ember-500 pl-3">
                <div className="font-display font-semibold">{f.label}</div>
                <div className="text-ink-300 text-xs">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 右：登录卡片 */}
        <Card className="lk-card !shadow-deep" variant="borderless">
          <div className="mb-6 text-center md:hidden">
            <div className="font-display font-bold text-2xl text-ink-900">LKML Patent</div>
            <div className="text-ink-500 text-sm">性能优化专利挖掘平台</div>
          </div>
          <h2 className="font-display text-2xl font-bold text-ink-900 mb-1">欢迎回来</h2>
          <p className="text-ink-500 text-sm mb-6">请输入您的账号登录</p>

          <Form layout="vertical" onFinish={handleSubmit} size="large" requiredMark={false}>
            <Form.Item
              name="username"
              rules={[{ required: true, message: "请输入用户名" }]}
            >
              <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: "请输入密码" }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="密码"
                autoComplete="current-password"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              className="lk-btn-ember !h-11"
            >
              登 录
            </Button>
          </Form>

          <div className="mt-6 pt-4 border-t border-ink-100 text-xs text-ink-400 text-center">
            <MailOutlined className="mr-1" />
            首次部署请通过环境变量 INIT_ADMIN_* 配置管理员账号
          </div>
        </Card>
      </div>
    </div>
  );
}
