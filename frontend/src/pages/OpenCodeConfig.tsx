import { useCallback, useEffect, useState } from "react";
import { Tabs, Spin } from "antd";
import { opencodeApi } from "@/api/opencode";
import type { OpenCodeConfig } from "@/types";
import BasicConfigTab from "@/components/OpenCode/BasicConfigTab";
import SkillsTab from "@/components/OpenCode/SkillsTab";
import PromptTemplatesTab from "@/components/OpenCode/PromptTemplatesTab";
import TestTab from "@/components/OpenCode/TestTab";

export default function OpenCodeConfig() {
  const [config, setConfig] = useState<OpenCodeConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await opencodeApi.getConfig();
      setConfig(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !config) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex justify-center py-24 text-ink-500">配置加载失败</div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink-900 mb-1">
          OpenCode 配置中心
        </h1>
        <p className="text-ink-500 text-sm">
          管理 OpenCode API 凭据、Skills 技能库、提示词模板，并验证连通性
        </p>
      </div>

      <Tabs
        defaultActiveKey="basic"
        items={[
          {
            key: "basic",
            label: "基础配置",
            children: <BasicConfigTab config={config} onUpdated={load} />,
          },
          {
            key: "skills",
            label: "Skills 管理",
            children: <SkillsTab />,
          },
          {
            key: "prompts",
            label: "提示词模板",
            children: <PromptTemplatesTab config={config} onUpdated={load} />,
          },
          {
            key: "test",
            label: "测试",
            children: <TestTab />,
          },
        ]}
      />
    </div>
  );
}
