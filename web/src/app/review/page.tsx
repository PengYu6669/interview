"use client";

import { AlertTriangle, ArrowLeft, ArrowRight, FileCheck2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { PageIntro, PageShell, StatusBadge } from "@/components/page-shell";
import {
  ReviewMaterial,
  REVIEW_MATERIAL_STORAGE_KEY,
  reviewMaterialSchema,
} from "@/lib/document-parse";
import {
  ResumeExtractionResult,
  RESUME_EXTRACTION_STORAGE_KEY,
  resumeExtractionCacheSchema,
  resumeExtractionFingerprint,
  resumeExtractionResultSchema,
} from "@/lib/resume-extraction";
import { StructuredProfile } from "@/features/resume-review/structured-profile";
import { InterviewFlowProgress } from "@/features/interview-flow/flow-progress";
import { Button } from "@/components/ui/button";
import { trainingDraftSchema } from "@/lib/training-draft";

export default function ReviewPage() {
  return (
    <Suspense fallback={<ReviewPageLoading />}>
      <ReviewContent />
    </Suspense>
  );
}

function ReviewPageLoading() {
  return (
    <PageShell active="new">
      <main className="content-container review-page">
        <p className="text-sm text-[var(--muted)]">正在读取本次材料…</p>
      </main>
    </PageShell>
  );
}

async function requestResumeExtraction(material: ReviewMaterial, resumeText: string) {
  const response = await fetch("/api/resumes/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resume_text: resumeText,
      jd: material.jd,
      target_role: material.role,
    }),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload ? String(payload.detail) : "结构化提取失败";
    throw new Error(detail);
  }
  return resumeExtractionResultSchema.parse(payload);
}

function ReviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [material, setMaterial] = useState<ReviewMaterial | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [loadError, setLoadError] = useState("");
  const [extraction, setExtraction] = useState<ResumeExtractionResult | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const initialization = window.setTimeout(() => {
      const raw = sessionStorage.getItem(REVIEW_MATERIAL_STORAGE_KEY);
      try {
        if (!raw) throw new Error("missing-session-material");
        const parsed = reviewMaterialSchema.parse(JSON.parse(raw));
        setMaterial(parsed);
        setResumeText(parsed.document.text);
        setLoadError("");
        const cachedRaw = sessionStorage.getItem(RESUME_EXTRACTION_STORAGE_KEY);
        if (cachedRaw) {
          void resumeExtractionFingerprint({ resumeText: parsed.document.text, jd: parsed.jd, targetRole: parsed.role }).then((fingerprint) => {
            try {
              const cached = resumeExtractionCacheSchema.parse(JSON.parse(cachedRaw));
              if (cached.fingerprint === fingerprint) setExtraction(cached.result);
            } catch {
              sessionStorage.removeItem(RESUME_EXTRACTION_STORAGE_KEY);
            }
          });
        }
      } catch {
        sessionStorage.removeItem(REVIEW_MATERIAL_STORAGE_KEY);
        const draftId = searchParams.get("draft");
        if (!draftId || !/^[0-9a-f-]{36}$/i.test(draftId)) {
          setLoadError("没有找到可恢复的材料，请返回准备页继续草稿或重新上传。");
          return;
        }
        void (async () => {
          try {
            const response = await fetch(`/api/drafts/${encodeURIComponent(draftId)}`, { cache: "no-store" });
            const payload: unknown = await response.json();
            if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练草稿读取失败");
            const draft = trainingDraftSchema.parse(payload);
            const restored = reviewMaterialSchema.parse({
              document: { filename: draft.resume_filename, media_type: "text/plain", text: draft.resume_text, page_count: null, warnings: ["已从 7 天训练草稿恢复提取文本；上传原文件未保留。"] },
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
              questionIds: draft.question_ids,
              questionTitles: draft.question_ids.map(() => "已选题目"),
              trainingFocus: draft.training_focus,
              sourceSessionId: draft.source_session_id ?? undefined,
              draftId: draft.id,
            });
            sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify(restored));
            setMaterial(restored);
            setResumeText(restored.document.text);
            setLoadError("");
            if (draft.extraction) {
              setExtracting(true);
              void requestResumeExtraction(restored, restored.document.text)
                .then(setExtraction)
                .catch((error: unknown) => setExtractionError(error instanceof Error ? error.message : "结构化结果读取失败"))
                .finally(() => setExtracting(false));
            }
          } catch (error) {
            setLoadError(error instanceof Error ? error.message : "训练草稿读取失败");
          }
        })();
      }
    }, 0);
    return () => window.clearTimeout(initialization);
  }, [searchParams]);

  async function cacheExtraction(result: ResumeExtractionResult) {
    if (!material) return;
    const fingerprint = await resumeExtractionFingerprint({ resumeText, jd: material.jd, targetRole: material.role });
    sessionStorage.setItem(RESUME_EXTRACTION_STORAGE_KEY, JSON.stringify({ fingerprint, result }));
  }

  async function createDraft(corrected: ReviewMaterial): Promise<string | null> {
    const response = await fetch("/api/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_filename: corrected.document.filename, resume_text: corrected.document.text, jd: corrected.jd, target_role: corrected.role, target_company: corrected.company, target_level: corrected.level, interview_round: corrected.interviewRound, interview_type: corrected.interviewType, mode: corrected.mode, duration_minutes: corrected.duration, pressure_level: corrected.pressure, depth_level: corrected.depth, guidance_level: corrected.guidance, question_ids: corrected.questionIds, training_focus: corrected.trainingFocus, source_session_id: corrected.sourceSessionId }) });
    if (response.status === 401) {
      router.push("/login?next=/review");
      return null;
    }
    const payload: unknown = await response.json();
    if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练草稿保存失败");
    const id = typeof payload === "object" && payload && "id" in payload ? String(payload.id) : "";
    if (!id) throw new Error("训练草稿返回了无效编号");
    const savedMaterial = { ...corrected, draftId: id };
    setMaterial(savedMaterial);
    sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify(savedMaterial));
    return id;
  }

  async function continueToBlueprint() {
    if (!material || !extraction) return;
    const validatedExtraction = resumeExtractionResultSchema.safeParse(extraction);
    if (!validatedExtraction.success) {
      setExtractionError("结构化结果存在空白或超长内容，请检查候选人摘要、技能和项目后再继续。");
      return;
    }
    setSaving(true);
    setExtractionError("");
    const corrected = { ...material, document: { ...material.document, text: resumeText } };
    sessionStorage.setItem(REVIEW_MATERIAL_STORAGE_KEY, JSON.stringify(corrected));
    await cacheExtraction(extraction);
    try {
      let draftId = material.draftId;
      if (!draftId) {
        draftId = await createDraft(corrected) ?? undefined;
        if (!draftId) return;
      }
      let updateResponse = await fetch(`/api/drafts/${draftId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_text: resumeText, extraction: extraction.profile }) });
      if (updateResponse.status === 404 || updateResponse.status === 409) {
        draftId = await createDraft(corrected) ?? undefined;
        if (!draftId) return;
        updateResponse = await fetch(`/api/drafts/${draftId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_text: resumeText, extraction: extraction.profile }) });
      }
      const updatePayload: unknown = await updateResponse.json();
      if (!updateResponse.ok) throw new Error(typeof updatePayload === "object" && updatePayload && "detail" in updatePayload ? String(updatePayload.detail) : "结构化结果保存失败");
      router.push("/blueprint");
    } catch (error) {
      setExtractionError(error instanceof Error ? error.message : "结构化结果保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function extractProfile(
    sourceMaterial: ReviewMaterial | null = material,
    sourceResumeText = resumeText,
  ) {
    if (!sourceMaterial || !sourceResumeText.trim()) return;
    setExtracting(true);
    setExtractionError("");
    try {
      const parsed = await requestResumeExtraction(sourceMaterial, sourceResumeText);
      setExtraction(parsed);
      await cacheExtraction(parsed);
    } catch (error) {
      setExtractionError(error instanceof Error ? error.message : "结构化提取失败");
    } finally {
      setExtracting(false);
    }
  }

  return (
    <PageShell active="new">
      <main className="content-container review-page">
        <PageIntro
          eyebrow="步骤 2 / 3 · 材料校正"
          title="确认简历文本是否完整"
          actions={material ? <StatusBadge tone={material.document.warnings.length ? "warning" : "success"}><FileCheck2 size={13} />真实解析结果</StatusBadge> : undefined}
        />
        <InterviewFlowProgress current={2} />

        {loadError ? (
          <section className="flow-error-state" role="alert"><AlertTriangle size={22} /><div><h2>无法读取材料</h2><p>{loadError}</p></div><Button asChild><Link href="/setup"><ArrowLeft size={15} />返回准备材料</Link></Button></section>
        ) : material ? (
          <div className="review-layout">
            <aside className="source-preview">
              <div className="panel-heading"><div><span>文件信息</span><small>{material.document.filename}</small></div></div>
              <div className="resume-paper">
                <h2>{material.role}</h2>
                <h3>解析信息</h3>
                <p>格式：{material.document.media_type}</p>
                <p>页数：{material.document.page_count ?? "不适用"}</p>
                <h3>岗位描述</h3>
                <p>{material.jd}</p>
                {material.document.warnings.map((warning) => <p key={warning} className="text-[var(--warning)]">注意：{warning}</p>)}
              </div>
            </aside>

            <div className="review-fields">
              <section className="review-block">
                <div className="review-block-title"><div><h2>简历原文</h2><p>先修正文档解析问题，再进行 AI 结构化提取</p></div></div>
                <div className="review-block-content">
                  <label className="field-label" htmlFor="resume-text">提取文本</label>
                  <textarea id="resume-text" className="answer-box" value={resumeText} onChange={(event) => { setResumeText(event.target.value); setExtraction(null); }} rows={18} />
                  {!resumeText.trim() && <p className="text-xs text-[var(--danger)]" role="alert">没有可用文本。扫描版 PDF 需要 OCR，当前不能继续。</p>}
                  {extractionError && <p className="text-xs text-[var(--danger)]" role="alert">{extractionError}</p>}
                  <Button type="button" disabled={!resumeText.trim() || extracting} onClick={() => void extractProfile()}><Sparkles size={15} />{extracting ? "正在读取结构化结果" : extraction ? "重新提取" : "开始结构化提取"}</Button>
                </div>
              </section>
              {extraction && <StructuredProfile result={extraction} onChange={setExtraction} />}
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">正在读取本次材料…</p>
        )}

        {material && (
          <div className="sticky-action-bar">
            <Button asChild variant="secondary"><Link href="/setup"><ArrowLeft size={16} />返回修改材料</Link></Button>
            <div><span>{extraction ? "结构化结果已通过校验" : "完成结构化提取后才能继续"}</span><Button type="button" disabled={!extraction || saving} onClick={() => void continueToBlueprint()}>{saving ? "正在保存" : "保存校正并继续"} <ArrowRight size={16} /></Button></div>
          </div>
        )}
      </main>
    </PageShell>
  );
}
