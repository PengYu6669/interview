import {
  INTERVIEW_TYPE_OPTIONS,
  InterviewRound,
  InterviewType,
  LEVEL_OPTIONS,
  ROUND_OPTIONS,
  TargetLevel,
} from "@/lib/training-context";
import { z } from "zod";

export type InterviewMode = "relaxed" | "normal" | "stress";
export { INTERVIEW_TYPE_OPTIONS, LEVEL_OPTIONS, ROUND_OPTIONS };
export type { InterviewRound, InterviewType, TargetLevel };

export interface ModeOption {
  value: InterviewMode;
  label: string;
  description: string;
}

export const MODE_OPTIONS: ModeOption[] = [
  { value: "relaxed", label: "引导模式", description: "适合熟悉流程" },
  { value: "normal", label: "标准模式", description: "接近常规技术面" },
  { value: "stress", label: "压力模式", description: "更严格的时间与追问" },
];

export const MODE_LEVELS: Record<InterviewMode, Pick<SetupState, "pressure" | "depth" | "guidance">> = {
  relaxed: { pressure: 1, depth: 3, guidance: 5 },
  normal: { pressure: 3, depth: 4, guidance: 3 },
  stress: { pressure: 5, depth: 5, guidance: 1 },
};

export const DURATION_OPTIONS = [20, 30, 45, 60] as const;

export interface SetupState {
  resumeName: string;
  jd: string;
  role: string;
  company: string;
  level: TargetLevel;
  interviewRound: InterviewRound;
  interviewType: InterviewType;
  mode: InterviewMode;
  duration: number;
  pressure: number;
  depth: number;
  guidance: number;
  selectedQuestions: Array<{ id: string; title: string }>;
  trainingFocus: string;
}

export const SETUP_STATE_STORAGE_KEY = "interview-copilot.setup-state.v1";

const setupStateSchema: z.ZodType<SetupState> = z.object({
  resumeName: z.string().max(255),
  jd: z.string().max(30_000),
  role: z.string().max(150),
  company: z.string().max(100),
  level: z.enum(["intern", "campus", "mid", "senior"]),
  interviewRound: z.enum(["first", "second", "final", "manager"]),
  interviewType: z.enum(["comprehensive", "project", "technical", "system_design", "behavioral", "weak_area"]),
  mode: z.enum(["relaxed", "normal", "stress"]),
  duration: z.number().int().min(1).max(180),
  pressure: z.number().int().min(1).max(5),
  depth: z.number().int().min(1).max(5),
  guidance: z.number().int().min(1).max(5),
  selectedQuestions: z.array(z.object({ id: z.string().uuid(), title: z.string().max(200) })).max(20),
  trainingFocus: z.string().max(500),
});

export function readSetupState(raw: string | null): SetupState | null {
  if (!raw) return null;
  try {
    const parsed = setupStateSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

export function serializeSetupState(state: SetupState): string {
  return JSON.stringify(setupStateSchema.parse(state));
}

export type DocumentParseStatus = "idle" | "parsing" | "success" | "error";

export function calculateReadiness(state: Pick<SetupState, "resumeName" | "jd" | "role">) {
  const requirements = [
    Boolean(state.resumeName),
    state.jd.trim().length >= 30,
    Boolean(state.role.trim()),
  ];
  return Math.round((requirements.filter(Boolean).length / requirements.length) * 100);
}
