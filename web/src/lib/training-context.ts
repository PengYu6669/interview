import type { components } from "./api-schema";

type InterviewContextContract = components["schemas"]["InterviewSessionData"];

export type TargetLevel = InterviewContextContract["target_level"];
export type InterviewRound = InterviewContextContract["interview_round"];
export type InterviewType = InterviewContextContract["interview_type"];

export const LEVEL_OPTIONS: Array<{ value: TargetLevel; label: string }> = [
  { value: "intern", label: "实习" },
  { value: "campus", label: "校招 / 初级" },
  { value: "mid", label: "中级" },
  { value: "senior", label: "高级" },
];

export const ROUND_OPTIONS: Array<{ value: InterviewRound; label: string }> = [
  { value: "first", label: "技术一面" },
  { value: "second", label: "技术二面" },
  { value: "manager", label: "主管面" },
  { value: "final", label: "终面" },
];

export const INTERVIEW_TYPE_OPTIONS: Array<{
  value: InterviewType;
  label: string;
  description: string;
}> = [
  { value: "comprehensive", label: "综合模拟", description: "按真实流程覆盖多个阶段" },
  { value: "project", label: "项目深挖", description: "聚焦职责、指标与技术取舍" },
  { value: "technical", label: "技术专项", description: "围绕岗位核心技术追问" },
  { value: "system_design", label: "系统设计", description: "训练估算、架构与故障治理" },
  { value: "coding", label: "手撕算法", description: "在模拟面试中完成 Python 算法题" },
  { value: "behavioral", label: "行为面试", description: "训练协作、冲突与推动能力" },
  { value: "weak_area", label: "弱项复训", description: "围绕历史改进项重新验证" },
];

export function trainingContextLabels(context: {
  target_level: TargetLevel;
  interview_round: InterviewRound;
  interview_type: InterviewType;
}) {
  return {
    level: LEVEL_OPTIONS.find((item) => item.value === context.target_level)?.label ?? context.target_level,
    round: ROUND_OPTIONS.find((item) => item.value === context.interview_round)?.label ?? context.interview_round,
    type: INTERVIEW_TYPE_OPTIONS.find((item) => item.value === context.interview_type)?.label ?? context.interview_type,
  };
}
