// 阶段配色（与 tailwind stage.s1..s4 一致），用 inline style 规避 Tailwind purge 动态类名问题
export const STAGE_COLORS: Record<1 | 2 | 3 | 4, string> = {
  1: "#3B82F6",
  2: "#8B5CF6",
  3: "#F59E0B",
  4: "#10B981",
};

export const STAGE_COLOR_SOFT: Record<1 | 2 | 3 | 4, string> = {
  1: "#DBEAFE",
  2: "#EDE9FE",
  3: "#FEF3C7",
  4: "#D1FAE5",
};
