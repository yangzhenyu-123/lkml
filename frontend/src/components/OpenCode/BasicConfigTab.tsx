import { useEffect, useState } from "react";
import {
  Card,
  Form,
  Input,
  InputNumber,
  Button,
  Tag,
  Space,
  App,
} from "antd";
import { PlusOutlined, DeleteOutlined, SaveOutlined } from "@ant-design/icons";
import { opencodeApi } from "@/api/opencode";
import type { OpenCodeConfig, OpenCodeConfigUpdate } from "@/types";

interface EnvItem {
  key: string;
  value: string;
}

interface FormValues {
  api_base: string;
  api_key: string;
  model: string;
  timeout: number;
  max_tokens: number;
  env: EnvItem[];
}

export default function BasicConfigTab({
  config,
  onUpdated,
}: {
  config: OpenCodeConfig;
  onUpdated: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const envEntries: EnvItem[] = Object.entries(config.env_json || {}).map(
      ([key, value]) => ({ key, value }),
    );
    form.setFieldsValue({
      api_base: config.api_base,
      api_key: "",
      model: config.model,
      timeout: config.timeout,
      max_tokens: config.max_tokens,
      env: envEntries,
    });
  }, [config, form]);

  const handleSave = async (values: FormValues) => {
    const env_json: Record<string, string> = {};
    (values.env || []).forEach((item) => {
      if (item && item.key) env_json[item.key] = item.value || "";
    });
    const payload: OpenCodeConfigUpdate = {
      api_base: values.api_base,
      model: values.model,
      timeout: values.timeout,
      max_tokens: values.max_tokens,
      env_json,
    };
    if (values.api_key) payload.api_key = values.api_key;

    setSaving(true);
    try {
      await opencodeApi.updateConfig(payload);
      message.success("配置已保存");
      onUpdated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="lk-card" variant="borderless">
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        requiredMark={false}
        className="max-w-2xl"
      >
        <Form.Item
          label="API Base URL"
          name="api_base"
          rules={[{ required: true, message: "请输入 API Base URL" }]}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item
          label={
            <Space>
              <span>API Key</span>
              {config.api_key_set ? (
                <Tag color="success" className="!mr-0">
                  已配置
                </Tag>
              ) : (
                <Tag color="warning" className="!mr-0">
                  未配置
                </Tag>
              )}
            </Space>
          }
          name="api_key"
        >
          <Input.Password placeholder="已设置（留空不修改）" />
        </Form.Item>

        <Form.Item
          label="模型名"
          name="model"
          rules={[{ required: true, message: "请输入模型名" }]}
        >
          <Input placeholder="gpt-4o" />
        </Form.Item>

        <div className="grid grid-cols-2 gap-4">
          <Form.Item
            label="超时秒数"
            name="timeout"
            rules={[{ required: true, message: "请输入超时秒数" }]}
          >
            <InputNumber min={10} max={3600} className="!w-full" />
          </Form.Item>
          <Form.Item
            label="最大 Token"
            name="max_tokens"
            rules={[{ required: true, message: "请输入最大 Token" }]}
          >
            <InputNumber min={256} max={128000} className="!w-full" />
          </Form.Item>
        </div>

        <div className="mb-2 text-sm font-medium text-ink-700">环境变量</div>
        <Form.List name="env">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space
                  key={key}
                  className="mb-2 !flex items-center"
                  align="baseline"
                >
                  <Form.Item {...restField} name={[name, "key"]} noStyle>
                    <Input placeholder="变量名" style={{ width: 200 }} />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, "value"]} noStyle>
                    <Input placeholder="变量值" style={{ width: 320 }} />
                  </Form.Item>
                  <DeleteOutlined
                    className="text-ink-400 hover:text-ember-500 cursor-pointer"
                    onClick={() => remove(name)}
                  />
                </Space>
              ))}
              <Button
                type="dashed"
                icon={<PlusOutlined />}
                onClick={() => add()}
              >
                添加变量
              </Button>
            </>
          )}
        </Form.List>

        <div className="mt-6">
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined />}
            loading={saving}
            className="lk-btn-ember"
          >
            保存配置
          </Button>
        </div>
      </Form>
    </Card>
  );
}
