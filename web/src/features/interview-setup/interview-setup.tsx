"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { MaterialsSection } from "./materials-section";
import { ParsedDocument, parsedDocumentSchema, readRetrainingContext, RETRAINING_FOCUS_STORAGE_KEY, REVIEW_MATERIAL_STORAGE_KEY, reviewMaterialSchema } from "@/lib/document-parse";
import { calculateReadiness, DocumentParseStatus, InterviewMode, MODE_LEVELS, readSetupState, serializeSetupState, SETUP_STATE_STORAGE_KEY, SetupState } from "./model";
import { SetupSummary } from "./setup-summary";
import { SetupIntro } from "./setup-intro";
import { TargetSection } from "./target-section";
import { QUESTION_INTERVIEW_SELECTION_KEY } from "@/lib/questions";
import Link from "next/link";
import { InterviewFlowProgress } from "@/features/interview-flow/flow-progress";
import { TrainingDraft } from "@/lib/training-draft";
import { DraftRecovery } from "./draft-recovery";

export function InterviewSetup({ careerPlanItemId }: { careerPlanItemId?: string }) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<SetupState>({
    resumeName: "",
    jd: "",
    role: "",
    company: "",
    level: "campus",
    interviewRound: "first",
    interviewType: "comprehensive",
    mode: "normal",
    duration: 30,
    pressure: 3,
    depth: 4,
    guidance: 3,
    selectedQuestions: [],
    trainingFocus: "",
  });
  const [parsedDocument, setParsedDocument] = useState<ParsedDocument | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [parseStatus, setParseStatus] = useState<DocumentParseStatus>("idle");
  const [parseError, setParseError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [sourceSessionId, setSourceSessionId] = useState<string | null>(null);
  const [linkedPlanItemId, setLinkedPlanItemId] = useState<string | null>(careerPlanItemId ?? null);
  const readiness = useMemo(() => calculateReadiness(state), [state]);

  useEffect(() => {
    const initialization = window.setTimeout(() => {
      let selectedQuestions: Array<{ id: string; title: string }> = [];
      const retraining = readRetrainingContext(sessionStorage.getItem(RETRAINING_FOCUS_STORAGE_KEY));
      sessionStorage.removeItem(RETRAINING_FOCUS_STORAGE_KEY);
      const trainingFocus = retraining?.focus ?? "";
      setSourceSessionId(retraining?.source_session_id ?? null);
      const selectionRaw = sessionStorage.getItem(QUESTION_INTERVIEW_SELECTION_KEY);
      if (selectionRaw) {
        try {
          const selection = JSON.parse(selectionRaw) as { questions?: Array<{ id?: string; title?: string }> };
          selectedQuestions = (selection.questions ?? []).filter((item): item is { id: string; title: string } => typeof item.id === "string" && typeof item.title === "string").slice(0, 20);
        } catch {
          sessionStorage.removeItem(QUESTION_INTERVIEW_SELECTION_KEY);
        }
      }
      const raw = sessionStorage.getItem(REVIEW_MATERIAL_STORAGE_KEY);
      const cachedState = readSetupState(sessionStorage.getItem(SETUP_STATE_STORAGE_KEY));
      if (!raw) {
        setState((current) => {
          const base = cachedState ?? current;
          return {
            ...base,
            role: retraining?.target_role ?? base.role,
            company: retraining?.target_company ?? base.company,
            level: retraining?.target_level ?? base.level,
            interviewRound: retraining?.interview_round ?? base.interviewRound,
            interviewType: retraining ? "weak_area" : base.interviewType,
            mode: retraining?.mode ?? base.mode,
            pressure: retraining?.pressure_level ?? base.pressure,
            depth: retraining?.depth_level ?? base.depth,
            guidance: retraining?.guidance_level ?? base.guidance,
            selectedQuestions: selectedQuestions.length ? selectedQuestions : base.selectedQuestions,
            trainingFocus: trainingFocus || base.trainingFocus,
          };
        });
        setHydrated(true);
        return;
      }
      try {
        const material = reviewMaterialSchema.parse(JSON.parse(raw));
        setParsedDocument(material.document);
        setSourceSessionId(retraining?.source_session_id ?? material.sourceSessionId ?? null);
        setDraftId(material.draftId ?? null);
        setParseStatus("success");
        setState({
          resumeName: material.document.filename,
          jd: material.jd ?? "",
          role: retraining?.target_role ?? material.role,
          company: retraining?.target_company ?? material.company,
          level: retraining?.target_level ?? material.level,
          interviewRound: retraining?.interview_round ?? material.interviewRound,
          interviewType: retraining ? "weak_area" : material.interviewType,
          mode: retraining?.mode ?? material.mode,
          duration: material.duration,
          pressure: retraining?.pressure_level ?? material.pressure,
          depth: retraining?.depth_level ?? material.depth,
          guidance: retraining?.guidance_level ?? material.guidance,
          selectedQuestions: selectedQuestions.length ? selectedQuestions : material.questionIds.map((id, index) => ({ id, title: material.questionTitles[index] ?? "已选题目" })),
          trainingFocus: trainingFocus || material.trainingFocus,
        });
      } catch {
        sessionStorage.removeItem(REVIEW_MATERIAL_STORAGE_KEY);
      } finally {
        setHydrated(true);
      }
    }, 0);
    return () => window.clearTimeout(initialization);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const timer = window.setTimeout(() => {
      sessionStorage.setItem(SETUP_STATE_STORAGE_KEY, serializeSetupState(state));
      if (parsedDocument) {
        sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify({
          document: parsedDocument,
          jd: state.jd,
          role: state.role,
          company: state.company,
          level: state.level,
          interviewRound: state.interviewRound,
          interviewType: state.interviewType,
          mode: state.mode,
          duration: state.duration,
          pressure: state.pressure,
          depth: state.depth,
          guidance: state.guidance,
          questionIds: state.selectedQuestions.map((item) => item.id),
          questionTitles: state.selectedQuestions.map((item) => item.title),
            trainingFocus: state.trainingFocus,
            sourceSessionId: sourceSessionId ?? undefined,
            draftId: draftId ?? undefined,
        }));
      }
    }, 200);
    return () => window.clearTimeout(timer);
  }, [draftId, hydrated, parsedDocument, sourceSessionId, state]);

  function update<K extends keyof SetupState>(key: K, value: SetupState[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function resumeDraft(draft: TrainingDraft) {
    const document: ParsedDocument = {
      filename: draft.resume_filename,
      media_type: "text/plain",
      text: draft.resume_text,
      page_count: null,
      warnings: ["已从训练草稿恢复提取文本；上传原文件未保留。"],
    };
    sessionStorage.removeItem(QUESTION_INTERVIEW_SELECTION_KEY);
    setParsedDocument(document);
    setDraftId(draft.id);
    setSourceSessionId(draft.source_session_id);
    setLinkedPlanItemId(draft.career_plan_item_id);
    setParseStatus("success");
    setParseError("");
    setSaveError("");
    setState({
      resumeName: draft.resume_filename,
      jd: draft.jd,
      role: draft.target_role,
      company: draft.target_company,
      level: draft.target_level,
      interviewRound: draft.interview_round,
      interviewType: draft.interview_type,
      mode: draft.mode,
      duration: draft.duration_minutes,
      pressure: draft.pressure_level,
      depth: draft.depth_level,
      guidance: draft.guidance_level,
      selectedQuestions: draft.question_ids.map((id) => ({ id, title: "已选题目" })),
      trainingFocus: draft.training_focus,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleFile(file: File) {
    update("resumeName", file.name);
    setParsedDocument(null);
    setDraftId(null);
    setParseError("");
    setParseStatus("parsing");

    const formData = new FormData();
    formData.set("file", file);
    try {
      const response = await fetch("/api/documents/parse", { method: "POST", body: formData });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const detail = typeof payload === "object" && payload !== null && "detail" in payload
          ? String(payload.detail)
          : "简历解析失败";
        throw new Error(detail);
      }
      setParsedDocument(parsedDocumentSchema.parse(payload));
      setParseStatus("success");
    } catch (error) {
      setParseStatus("error");
      setParseError(error instanceof Error ? error.message : "简历解析失败");
    }
  }

  async function continueToReview() {
    if (!parsedDocument) return;
    setSaving(true);
    setSaveError("");
    const material = {
      document: parsedDocument,
      jd: state.jd,
      role: state.role,
      company: state.company,
      level: state.level,
      interviewRound: state.interviewRound,
      interviewType: state.interviewType,
      mode: state.mode,
      duration: state.duration,
      pressure: state.pressure,
      depth: state.depth,
      guidance: state.guidance,
      questionIds: state.selectedQuestions.map((item) => item.id),
      questionTitles: state.selectedQuestions.map((item) => item.title),
      trainingFocus: state.trainingFocus,
      sourceSessionId: sourceSessionId ?? undefined,
    };
    sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify({ ...material, draftId: draftId ?? undefined }));
    try {
      let nextDraftId = draftId;
      const payload = { resume_filename: parsedDocument.filename, resume_text: parsedDocument.text, jd: state.jd, target_role: state.role, target_company: state.company, target_level: state.level, interview_round: state.interviewRound, interview_type: state.interviewType, mode: state.mode, duration_minutes: state.duration, pressure_level: state.pressure, depth_level: state.depth, guidance_level: state.guidance, question_ids: state.selectedQuestions.map((item) => item.id), training_focus: state.trainingFocus, source_session_id: sourceSessionId, career_plan_item_id: linkedPlanItemId };
      let response = draftId
        ? await fetch(`/api/drafts/${encodeURIComponent(draftId)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
        : await fetch("/api/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (draftId && (response.status === 404 || response.status === 409)) {
        response = await fetch("/api/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      }
      if (response.ok) {
        const draft = await response.json() as { id?: string };
        if (!draft.id) throw new Error("训练草稿返回了无效编号");
        nextDraftId = draft.id;
        setDraftId(draft.id);
        sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify({ ...material, draftId: draft.id }));
      } else if (response.status !== 401) {
        const payload: unknown = await response.json();
        const detail = typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练草稿保存失败";
        throw new Error(detail);
      }
      router.push(nextDraftId ? `/review?draft=${encodeURIComponent(nextDraftId)}` : "/review");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "训练草稿保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader active="new" />
      <main className="setup-page">
        <SetupIntro />
        <DraftRecovery onResume={resumeDraft} />
        <InterviewFlowProgress current={1} />
        {sourceSessionId && <section className="retraining-brief"><div><span>弱项复训来源</span><h2>这一次不是重新做题，而是验证上次缺口</h2><p>{state.trainingFocus}</p></div><Link href={`/report?session=${sourceSessionId}`}>查看来源证据</Link></section>}
        <div className="setup-workspace">
        <section className="min-w-0">
          <div className="space-y-5">
            <MaterialsSection
              resumeName={state.resumeName}
              jd={state.jd}
              fileInputRef={fileInputRef}
              onFileSelected={handleFile}
              onJdChange={(value) => update("jd", value)}
              parseStatus={parseStatus}
              parseError={parseError}
            />
            <TargetSection
              role={state.role}
              company={state.company}
              level={state.level}
              interviewRound={state.interviewRound}
              interviewType={state.interviewType}
              mode={state.mode}
              duration={state.duration}
              pressure={state.pressure}
              depth={state.depth}
              guidance={state.guidance}
              trainingFocus={state.trainingFocus}
              onRoleChange={(value) => update("role", value)}
              onCompanyChange={(value) => update("company", value)}
              onLevelChange={(value) => update("level", value)}
              onInterviewRoundChange={(value) => update("interviewRound", value)}
              onInterviewTypeChange={(value) => update("interviewType", value)}
              onModeChange={(value: InterviewMode) => setState((current) => ({ ...current, mode: value, ...MODE_LEVELS[value] }))}
              onDurationChange={(value) => update("duration", value)}
              onPressureChange={(value) => update("pressure", value)}
              onDepthChange={(value) => update("depth", value)}
              onGuidanceChange={(value) => update("guidance", value)}
              onTrainingFocusChange={(value) => update("trainingFocus", value)}
            />
          </div>
        </section>
        <SetupSummary state={state} readiness={readiness} parseStatus={parseStatus} onContinue={continueToReview} saving={saving} saveError={saveError} />
        </div>
      </main>
    </div>
  );
}
