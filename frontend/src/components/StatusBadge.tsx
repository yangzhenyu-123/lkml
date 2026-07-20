import { Tag } from "antd";
import type { ItemStatus, JobStatus } from "@/types";
import { itemStatusMap, jobStatusMap } from "@/utils/format";

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const m = jobStatusMap[status];
  return <Tag color={m.color}>{m.text}</Tag>;
}

export function ItemStatusBadge({ status }: { status: ItemStatus }) {
  const m = itemStatusMap[status];
  return <Tag color={m.color}>{m.text}</Tag>;
}

export default ItemStatusBadge;
