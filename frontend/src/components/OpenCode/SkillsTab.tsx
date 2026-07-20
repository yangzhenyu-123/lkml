import { useEffect, useState } from "react";
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Switch,
  Tag,
  Alert,
  Popconfirm,
  Space,
  App,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import type { TableProps } from "antd";
import { opencodeApi } from "@/api/opencode";
import type { SkillConfig, SkillConfigCreate } from "@/types";

interface CreateValues {
  name: string;
  git_url: string;
  branch?: string;
  local_path?: string;
  enabled?: boolean;
}

export default function SkillsTab() {
  const { message } = App.useApp();
  const [items, setItems] = useState<SkillConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<CreateValues>();

  const load = async () => {
    setLoading(true);
    try {
      const data = await opencodeApi.listSkills();
      setItems(data.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: number) => {
    try {
      await opencodeApi.removeSkill(id);
      message.success("技能已删除");
      load();
    } catch {
      /* 错误已由拦截器提示 */
    }
  };

  const handleCreate = async (values: CreateValues) => {
    const payload: SkillConfigCreate = {
      name: values.name,
      git_url: values.git_url,
      branch: values.branch || "main",
      local_path: values.local_path,
      enabled: values.enabled ?? true,
    };
    setCreating(true);
    try {
      await opencodeApi.createSkill(payload);
      message.success("技能已添加");
      setModalOpen(false);
      form.resetFields();
      load();
    } finally {
      setCreating(false);
    }
  };

  const columns: TableProps<SkillConfig>["columns"] = [
    { title: "名称", dataIndex: "name", key: "name" },
    {
      title: "Git 仓库",
      dataIndex: "git_url",
      key: "git_url",
      render: (url: string) =>
        url ? (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="text-ember-600"
          >
            <LinkOutlined className="mr-1" />
            {url}
          </a>
        ) : (
          "—"
        ),
    },
    { title: "分支", dataIndex: "branch", key: "branch" },
    {
      title: "本地路径",
      dataIndex: "local_path",
      key: "local_path",
      render: (p: string) => p || "—",
    },
    {
      title: "启用",
      dataIndex: "enabled",
      key: "enabled",
      render: (v: boolean) =>
        v ? (
          <Tag color="success">启用</Tag>
        ) : (
          <Tag>停用</Tag>
        ),
    },
    {
      title: "操作",
      key: "action",
      render: (_, record) => (
        <Popconfirm
          title="确认删除该技能？"
          description={record.name}
          onConfirm={() => handleDelete(record.id)}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            size="small"
          />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <Alert
        type="info"
        showIcon
        message="预置技能已自动配置"
        description={
          <span>
            预置技能：<b>patent-disclosure-skill</b>（
            <a
              href="https://github.com/handsomestWei/patent-disclosure-skill"
              target="_blank"
              rel="noreferrer"
              className="text-ember-600"
            >
              https://github.com/handsomestWei/patent-disclosure-skill
            </a>
            ）已自动配置。
          </span>
        }
      />

      <Card
        className="lk-card"
        variant="borderless"
        title={<span className="font-display font-semibold">技能列表</span>}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            className="lk-btn-ember"
            onClick={() => setModalOpen(true)}
          >
            添加技能
          </Button>
        }
      >
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title="添加技能"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ branch: "main", enabled: true }}
        >
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: "请输入技能名称" }]}
          >
            <Input placeholder="my-skill" />
          </Form.Item>
          <Form.Item
            label="Git 仓库 URL"
            name="git_url"
            rules={[{ required: true, message: "请输入 Git 仓库地址" }]}
          >
            <Input placeholder="https://github.com/user/repo.git" />
          </Form.Item>
          <Form.Item label="分支" name="branch">
            <Input placeholder="main" />
          </Form.Item>
          <Form.Item label="本地路径（可选）" name="local_path">
            <Input placeholder="/data/skills/my-skill" />
          </Form.Item>
          <Form.Item label="启用" name="enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setModalOpen(false)}>取消</Button>
            <Button
              type="primary"
              htmlType="submit"
              loading={creating}
              className="lk-btn-ember"
            >
              添加
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
