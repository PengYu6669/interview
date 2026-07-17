import { RETRAINING_FOCUS_STORAGE_KEY, serializeRetrainingContext } from "./document-parse";
import { interviewReportSchema } from "./interview-report";

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

export async function prepareInterviewRetraining({
  sourceSessionId,
  focus,
  improvement,
}: {
  sourceSessionId: string;
  focus: string;
  improvement?: { skill: string; title: string };
}) {
  const response = await fetch(
    `/api/interview-sessions/${encodeURIComponent(sourceSessionId)}/report`,
    { cache: "no-store" },
  );
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(errorMessage(payload, "来源报告读取失败"));
  const report = interviewReportSchema.parse(payload);
  const mode = report.mode === "relaxed" || report.mode === "stress" ? report.mode : "normal";
  sessionStorage.setItem(RETRAINING_FOCUS_STORAGE_KEY, serializeRetrainingContext({
    focus,
    source_session_id: sourceSessionId,
    target_role: report.target_role,
    target_company: report.target_company,
    target_level: report.target_level,
    interview_round: report.interview_round,
    interview_type: "weak_area",
    mode,
    pressure_level: report.pressure_level,
    depth_level: report.depth_level,
    guidance_level: report.guidance_level,
    improvements: improvement ? [improvement] : [],
  }));
}
