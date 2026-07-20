import { useEffect, useState } from "react";
import {
  Alert, App, Button, Card, Form, Input, Modal, Popconfirm,
  Select, Space, Switch, Table, Tag, Tooltip,
} from "antd";
import type { TableColumnsType } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { usersApi } from "@/api/users";
import { useAuthStore } from "@/store/authStore";
import type { User, UserRole } from "@/types";
import { formatDateTime } from "@/utils/format";

const roleColor: Record<UserRole, string> = { admin: "red", analyst: "blue", viewer: "default" };
const roleLabel: Record<UserRole, string> = { admin: "管理员", analyst: "分析师", viewer: "观察者" };
const roleOptions = (["admin", "analyst", "viewer"] as UserRole[]).map((r) => ({
  value: r,
  label: `${roleLabel[r]}（${r}）`,
}));

interface CreateForm { username: string; email: string; password: string; role: UserRole; }
interface EditForm { email: string; role: UserRole; password?: string; }

export default function Users() {
  const { message } = App.useApp();
  const { user: currentUser } = useAuthStore();
  const [items, setItems] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createForm] = Form.useForm<CreateForm>();
  const [editForm] = Form.useForm<EditForm>();

  const load = async () => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await usersApi.list({ skip, limit: pageSize });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      // 错误已由 API 拦截器提示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [page, pageSize]);

  const openCreate = () => {
    createForm.resetFields();
    createForm.setFieldsValue({ role: "viewer" });
    setCreateOpen(true);
  };

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      setSubmitting(true);
      await usersApi.create(values);
      message.success("用户已创建");
      setCreateOpen(false);
      void load();
    } catch {
      // 校验失败或接口错误
    } finally {
      setSubmitting(false);
    }
  };

  const openEdit = (u: User) => {
    editForm.resetFields();
    editForm.setFieldsValue({ email: u.email, role: u.role, password: "" });
    setEditTarget(u);
  };

  const handleEdit = async () => {
    if (!editTarget) return;
    try {
      const values = await editForm.validateFields();
      setSubmitting(true);
      const patch: Partial<{ email: string; password: string; role: UserRole }> = {
        email: values.email,
        role: values.role,
      };
      if (values.password) patch.password = values.password;
      await usersApi.update(editTarget.id, patch);
      message.success("用户已更新");
      setEditTarget(null);
      void load();
    } catch {
      // 校验失败或接口错误
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (u: User, checked: boolean) => {
    try {
      await usersApi.update(u.id, { is_active: checked });
      message.success(checked ? "已启用" : "已停用");
      void load();
    } catch {
      // 错误已由 API 拦截器提示
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await usersApi.remove(id);
      message.success("用户已删除");
      void load();
    } catch {
      // 错误已由 API 拦截器提示
    }
  };

  const columns: TableColumnsType<User> = [
    { title: "用户名", dataIndex: "username", key: "username" },
    { title: "邮箱", dataIndex: "email", key: "email" },
    {
      title: "角色", dataIndex: "role", key: "role",
      render: (r: UserRole) => <Tag color={roleColor[r]}>{roleLabel[r]}</Tag>,
    },
    {
      title: "启用状态", dataIndex: "is_active", key: "is_active",
      render: (active: boolean, record) => (
        <Switch
          checked={active}
          onChange={(c) => handleToggleActive(record, c)}
          disabled={record.id === currentUser?.id}
        />
      ),
    },
    {
      title: "创建时间", dataIndex: "created_at", key: "created_at",
      render: (s: string) => formatDateTime(s),
    },
    {
      title: "操作", key: "actions", width: 120,
      render: (_, record) => {
        const isSelf = record.id === currentUser?.id;
        const deleteBtn = isSelf ? (
          <Tooltip title="不能删除当前登录用户">
            <Button type="text" danger icon={<DeleteOutlined />} size="small" disabled />
          </Tooltip>
        ) : (
          <Popconfirm
            title="删除用户"
            description="确定要删除该用户吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        );
        return (
          <Space>
            <Button type="text" icon={<EditOutlined />} size="small" onClick={() => openEdit(record)} />
            {deleteBtn}
          </Space>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900 m-0">用户管理</h1>
          <p className="text-ink-500 text-sm mt-1">管理系统用户与角色权限</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} className="lk-btn-ember" onClick={openCreate}>
          新增用户
        </Button>
      </div>

      {currentUser && (
        <Alert
          type="info"
          showIcon
          message={`您当前以 ${roleLabel[currentUser.role]}（${currentUser.role}）角色登录`}
        />
      )}

      <Card variant="borderless" className="lk-card">
        <Table<User>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 个用户`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Card>

      <Modal
        title="新增用户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        confirmLoading={submitting}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ className: "lk-btn-ember" }}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input placeholder="登录用户名" autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input placeholder="user@example.com" autoComplete="off" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password placeholder="初始密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: "请选择角色" }]}>
            <Select options={roleOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户：${editTarget?.username ?? ""}`}
        open={!!editTarget}
        onCancel={() => setEditTarget(null)}
        onOk={handleEdit}
        confirmLoading={submitting}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ className: "lk-btn-ember" }}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: "请选择角色" }]}>
            <Select options={roleOptions} />
          </Form.Item>
          <Form.Item name="password" label="新密码" extra="留空则不修改密码">
            <Input.Password placeholder="留空不修改" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
