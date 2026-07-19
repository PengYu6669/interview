"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiGetOptional, apiPatch, ApiError } from "@/lib/api-client";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { type WeeklyPlanItem, weeklyPlanItemSchema } from "@/lib/career";
import { CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";
import { prepareInterviewRetraining } from "@/lib/retraining";
import { TrainingDraftSummary, trainingDraftSummarySchema } from "@/lib/training-draft";

function localDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function statusLabel(status: CoachingSummary["status"]) {
  if (status === "completed") return "已完成";
  if (status === "active") return "进行中";
  return "待开始";
}

export type HubPhase = "loading" | "unconfigured" | "ready";

export function useTrainingHub() {
  const router = useRouter();
  const [recent, setRecent] = useState<CoachingSummary[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [profile, setProfile] = useState<AbilityProfileData | null>(null);
  const [today, setToday] = useState<WeeklyPlanItem[]>([]);
  const [drafts, setDrafts] = useState<TrainingDraftSummary[]>([]);
  const [contextLoading, setContextLoading] = useState(true);
  const [contextError, setContextError] = useState("");
  const [startingRecommendation, setStartingRecommendation] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");

  useEffect(() => {
    let mounted = true;

    void (async () => {
      try {
        const recentData = await apiGetOptional("/api/coaching-sessions", coachingSummarySchema);
        if (mounted && recentData) setRecent(recentData);
      } finally {
        if (mounted) setLoadingRecent(false);
      }
    })();

    void (async () => {
      try {
        const [profileResponse, todayResponse, draftsResponse] = await Promise.all([
          apiGetOptional("/api/profile", abilityProfileSchema),
          apiGetOptional(`/api/career/today?date=${localDate()}`, weeklyPlanItemSchema.array()),
          apiGetOptional("/api/drafts", trainingDraftSummarySchema.array()),
        ]);
        if (!mounted) return;
        if (profileResponse) setProfile(profileResponse);
        else setContextError("能力画像暂时无法读取。");
        if (todayResponse) setToday(todayResponse);
        if (draftsResponse) setDrafts(draftsResponse);
      } catch {
        if (mounted) setContextError("训练上下文暂时无法完整读取。");
      } finally {
        if (mounted) setContextLoading(false);
      }
    })();

    return () => { mounted = false; };
  }, []);

  async function startPlannedItem(item: WeeklyPlanItem) {
    if (item.task_type === "mock_interview") {
      router.push(`/setup?planItem=${item.id}`);
      return;
    }
    if (item.task_type === "question_review" && item.question_id) {
      if (item.plan_id && item.status === "pending") {
        try {
          await apiPatch(
            `/api/career/weekly-plan/${encodeURIComponent(item.plan_id)}/items/${encodeURIComponent(item.id)}`,
            { status: "in_progress" },
            weeklyPlanItemSchema,
          );
        } catch (caught) {
          setRecommendationError(caught instanceof ApiError ? caught.message : "今日任务暂时无法同步，请稍后重试");
          return;
        }
      }
      const query = item.plan_id ? `?plan=${item.plan_id}&planItem=${item.id}` : "";
      router.push(item.question_slug ? `/questions/${item.question_slug}${query}` : "/questions");
      return;
    }
    if (item.coaching_mode) {
      if (item.question_id) {
        const framework = item.exercise_type === "prep_pitch" ? "prep" : "star";
        sessionStorage.setItem(
          QUESTION_COACHING_SELECTION_KEY,
          JSON.stringify({ questions: [{ id: item.question_id, title: item.title, framework }] }),
        );
      }
      const query = new URLSearchParams({
        mode: item.coaching_mode,
        difficulty: item.difficulty ?? "guided",
        focus: item.completion_criteria,
        planItem: item.id,
      });
      router.push(`/training/new?${query.toString()}`);
      return;
    }
    router.push("/setup");
  }

  async function startWeaknessInterview() {
    const profileSourceSessionId = profile?.kline.at(-1)?.session_id;
    if (!profile?.next_training || !profileSourceSessionId) {
      router.push("/setup");
      return;
    }
    setStartingRecommendation(true);
    setRecommendationError("");
    try {
      await prepareInterviewRetraining({
        sourceSessionId: profileSourceSessionId,
        focus: profile.next_training,
      });
      router.push("/setup");
    } catch (caught) {
      setRecommendationError(caught instanceof Error ? caught.message : "暂时无法准备弱项复训");
    } finally {
      setStartingRecommendation(false);
    }
  }

  const latestDraft = drafts[0] ?? null;
  const interviewTask = today.find(
    (item) => item.task_type === "mock_interview" && item.status !== "completed" && item.status !== "skipped",
  );
  const otherTasks = today.filter((item) => item.id !== interviewTask?.id);
  const coaching = profile?.coaching;
  const profileSourceSessionId = profile?.kline.at(-1)?.session_id;
  const hasMaterials = Boolean(
    latestDraft?.target_role?.trim()
    || latestDraft?.resume_filename?.trim()
    || (profile?.report_count ?? 0) > 0,
  );
  const phase: HubPhase = contextLoading || loadingRecent
    ? "loading"
    : hasMaterials
      ? "ready"
      : "unconfigured";

  const activeDrill = recent.find((item) => item.status === "active");

  return {
    recent,
    loadingRecent,
    profile,
    today,
    drafts,
    contextLoading,
    contextError,
    startingRecommendation,
    recommendationError,
    latestDraft,
    interviewTask,
    otherTasks,
    coaching,
    profileSourceSessionId,
    hasMaterials,
    phase,
    activeDrill,
    startPlannedItem,
    startWeaknessInterview,
  };
}
