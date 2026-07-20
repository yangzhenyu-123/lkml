import { useState } from "react";
import { Modal, Tabs, Spin, Alert, Empty } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

interface Props {
  open: boolean;
  title: string;
  loading?: boolean;
  error?: string;
  content?: string;
  onClose: () => void;
  extraTabs?: { key: string; label: string; children: React.ReactNode }[];
}

/** 产出查看器：Markdown 渲染 + 额外 Tab（如日志、原始内容） */
export default function OutputViewer({
  open,
  title,
  loading,
  error,
  content,
  onClose,
  extraTabs = [],
}: Props) {
  const [activeKey, setActiveKey] = useState("preview");

  const tabs = [
    {
      key: "preview",
      label: "渲染预览",
      children: loading ? (
        <div className="py-12 text-center">
          <Spin />
        </div>
      ) : error ? (
        <Alert type="error" message={error} />
      ) : content ? (
        <div className="lk-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {content}
          </ReactMarkdown>
        </div>
      ) : (
        <Empty description="暂无内容" />
      ),
    },
    ...extraTabs,
  ];

  return (
    <Modal
      open={open}
      title={title}
      onCancel={onClose}
      footer={null}
      width={900}
      destroyOnClose
    >
      <Tabs activeKey={activeKey} onChange={setActiveKey} items={tabs} />
    </Modal>
  );
}
