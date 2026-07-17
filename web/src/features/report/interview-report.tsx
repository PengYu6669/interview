"use client";

import {
  AlertTriangle,
  ArrowLeft,
  AudioLines,
  BookOpenCheck,
  BriefcaseBusiness,
  Building2,
  Check,
  CheckCircle2,
  Code2,
  FileWarning,
  ExternalLink,
  Gauge,
  Keyboard,
  ListChecks,
  LoaderCircle,
  MessageSquareQuote,
  Plus,
  RefreshCw,
  RotateCcw,
  Scale,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PageIntro, StatusBadge } from "@/components/page-shell";
import { AiWorkReceipt } from "@/components/ai-work-receipt";
import { EvidenceChain } from "@/components/evidence-chain";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  RETRAINING_FOCUS_STORAGE_KEY,
  serializeRetrainingContext,
} from "@/lib/document-parse";
import {
  InterviewReportData,
  InterviewReportReviewData,
  interviewReportGenerationSchema,
  interviewReportReviewSchema,
  interviewReportSchema,
} from "@/lib/interview-report";
import { trainingContextLabels } from "@/lib/training-context";

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

type ReviewTarget = {
  skillIndex: number;
  skill: string;
  originalScore: number;
};

export function InterviewReport({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [report, setReport] = useState<InterviewReportData | null>(null);
  const [selectedImprovements, setSelectedImprovements] = useState<number[]>([]);
  const [phase, setPhase] = useState<"loading" | "generating" | "ready" | "error">(
    sessionId ? "loading" : "error",
  );
  const [generationMessage, setGenerationMessage] = useState("正在读取已保存的复盘报告");
  const [generationAttempt, setGenerationAttempt] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState(
    sessionId ? "" : "缺少面试会话，请从训练记录进入报告。",
  );
  const [reviewTarget, setReviewTarget] = useState<ReviewTarget | null>(null);
  const [reviewAction, setReviewAction] = useState<"reevaluate" | "exclude">("reevaluate");
  const [reviewReason, setReviewReason] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [sourceReport, setSourceReport] = useState<InterviewReportData | null>(null);
  const [sourceReportError, setSourceReportError] = useState<{ sourceId: string; message: string } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    const controller = new AbortController();

    async function readReport() {
      const response = await fetch(
        `/api/interview-sessions/${encodeURIComponent(sessionId)}/report`,
        { cache: "no-store", signal: controller.signal },
      );
      const payload: unknown = await response.json();
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(errorMessage(payload, "面试报告读取失败"));
      return interviewReportSchema.parse(payload);
    }

    async function readStatus() {
      const response = await fetch(
        `/api/interview-sessions/${encodeURIComponent(sessionId)}/report-status`,
        { cache: "no-store", signal: controller.signal },
      );
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "报告生成状态读取失败"));
      return interviewReportGenerationSchema.parse(payload);
    }

    function applyReport(parsed: InterviewReportData) {
      if (!active) return;
      setReport(parsed);
      setSelectedImprovements(parsed.content.improvements.map((_, index) => index));
      setPhase("ready");
    }

    async function pollUntilReady() {
      while (active) {
        const status = await readStatus();
        if (!active) return;
        setGenerationMessage(status.message);
        if (status.status === "failed") throw new Error(status.message);
        if (status.status === "ready") {
          const parsed = await readReport();
          if (parsed) {
            applyReport(parsed);
            return;
          }
        }
        await new Promise((resolve) => window.setTimeout(resolve, 2_000));
      }
    }

    async function load() {
      setError("");
      setReport(null);
      setPhase("loading");
      setElapsedSeconds(0);
      setGenerationMessage("正在读取已保存的复盘报告");
      const existing = await readReport();
      if (existing) {
        applyReport(existing);
        return;
      }
      const currentStatus = await readStatus();
      setPhase("generating");
      setGenerationMessage(currentStatus.message);
      if (currentStatus.status === "generating" || currentStatus.status === "ready") {
        await pollUntilReady();
        return;
      }
      const response = await fetch(
        `/api/interview-sessions/${encodeURIComponent(sessionId)}/report`,
        { method: "POST", signal: controller.signal },
      );
      const payload: unknown = await response.json();
      if (response.ok) {
        applyReport(interviewReportSchema.parse(payload));
        return;
      }
      const failure = new Error(errorMessage(payload, "面试报告生成失败"));
      const latestStatus = await readStatus();
      if (latestStatus.status === "generating" || latestStatus.status === "ready") {
        await pollUntilReady();
        return;
      }
      throw latestStatus.status === "failed" ? new Error(latestStatus.message) : failure;
    }
    void load()
      .catch((caught) => {
        if (active && !(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "面试报告生成失败");
          setPhase("error");
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [generationAttempt, sessionId]);

  useEffect(() => {
    if (phase !== "generating") return;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1_000));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    const sourceId = report?.source_session_id;
    if (!sourceId) return;
    let active = true;
    void fetch(`/api/interview-sessions/${encodeURIComponent(sourceId)}/report`, { cache: "no-store" })
      .then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(errorMessage(payload, "来源报告读取失败"));
        if (active) setSourceReport(interviewReportSchema.parse(payload));
      })
      .catch((caught) => {
        if (active) setSourceReportError({ sourceId, message: caught instanceof Error ? caught.message : "来源报告读取失败" });
      });
    return () => { active = false; };
  }, [report?.source_session_id]);

  if (phase === "loading" || phase === "generating") {
    return <ReportProcessState phase={phase} message={generationMessage} elapsedSeconds={elapsedSeconds} />;
  }
  if (error || !report) {
    return <main className="content-container"><section className="report-generating error" role="alert"><FileWarning size={28} /><span className="report-process-kicker">生成未完成</span><h1>复盘报告暂时不可用</h1><p>{error || "报告数据不存在"}</p><div className="report-process-actions"><Link href="/history" className="secondary-button"><ArrowLeft size={15} />返回训练记录</Link>{sessionId && <button type="button" className="primary-cta" onClick={() => setGenerationAttempt((value) => value + 1)}><RefreshCw size={15} />重新生成</button>}</div>{sessionId && <small>重新生成会复用同一场回答证据，成功后不会重复产生报告。</small>}</section></main>;
  }

  const partial = report.session_status === "ended";
  const context = trainingContextLabels(report);
  const keyFindings = [
    ...report.content.improvements.slice(0, 2).map((item) => ({ ...item, tone: "warning" as const, action: item.improvement ?? report.content.next_training })),
    ...report.content.strengths.slice(0, report.content.improvements.length >= 2 ? 1 : 3 - report.content.improvements.length).map((item) => ({ ...item, tone: "positive" as const, action: "在更高难度或新的追问情境中再次验证这一表现。" })),
  ];

  function toggleImprovement(index: number) {
    setSelectedImprovements((current) => current.includes(index)
      ? current.filter((item) => item !== index)
      : [...current, index].sort((left, right) => left - right));
  }

  function startRetraining() {
    if (!report) return;
    const improvements = selectedImprovements.map((index) => report.content.improvements[index]);
    const detail = improvements.length
      ? `重点改进：${improvements.map((item) => `${item.skill}：${item.title}`).join("；")}`
      : "";
    const focus = [report.content.next_training, detail].filter(Boolean).join("\n").slice(0, 500);
    const mode = report.mode === "relaxed" || report.mode === "stress" ? report.mode : "normal";
    sessionStorage.setItem(RETRAINING_FOCUS_STORAGE_KEY, serializeRetrainingContext({
      focus,
      source_session_id: report.session_id,
      target_role: report.target_role,
      target_company: report.target_company,
      target_level: report.target_level,
      interview_round: report.interview_round,
      interview_type: "weak_area",
      mode,
      pressure_level: report.pressure_level,
      depth_level: report.depth_level,
      guidance_level: report.guidance_level,
      improvements: improvements.map((item) => ({ skill: item.skill, title: item.title })),
    }));
    router.push("/setup");
  }

  function openReview(target: ReviewTarget) {
    setReviewTarget(target);
    setReviewAction("reevaluate");
    setReviewReason("");
    setReviewError("");
  }

  function latestReview(skillIndex: number) {
    return report?.reviews.filter((item) => item.skill_index === skillIndex).at(-1);
  }

  async function submitReview() {
    if (!report || !reviewTarget || reviewSubmitting) return;
    const reason = reviewReason.trim();
    if (reason.length < 10) {
      setReviewError("请至少用 10 个字说明你认为哪里需要重新核对");
      return;
    }
    setReviewSubmitting(true);
    setReviewError("");
    try {
      const response = await fetch(
        `/api/interview-sessions/${encodeURIComponent(report.session_id)}/report-reviews`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            client_request_id: crypto.randomUUID(),
            skill_index: reviewTarget.skillIndex,
            action: reviewAction,
            reason,
          }),
        },
      );
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "报告异议提交失败"));
      const review = interviewReportReviewSchema.parse(payload);
      setReport((current) => current ? { ...current, reviews: [...current.reviews, review] } : current);
      setReviewTarget(null);
    } catch (caught) {
      setReviewError(caught instanceof Error ? caught.message : "报告异议提交失败");
    } finally {
      setReviewSubmitting(false);
    }
  }

  return <main className="content-container report-page">
    <PageIntro
      eyebrow={`${partial ? "中途结束" : "训练完成"} · 证据覆盖 ${report.content.evidence_coverage}%`}
      title="本次面试报告"
      description={`${report.target_role} · ${report.duration_minutes} 分钟 · ${report.turn_count} 轮回答。评分只覆盖本场实际出现的回答证据。`}
      actions={<><Button asChild variant="secondary"><Link href="/history"><ArrowLeft size={15} />训练记录</Link></Button><Button type="button" onClick={startRetraining}><RotateCcw size={15} />按选中项复训</Button></>}
    />

    <section className="report-context-strip" aria-label="本场面试上下文">
      <div><Building2 size={16} /><span>目标公司</span><strong>{report.target_company || "未指定公司"}</strong></div>
      <div><BriefcaseBusiness size={16} /><span>岗位与职级</span><strong>{report.target_role} · {context.level}</strong></div>
      <div><ListChecks size={16} /><span>轮次与类型</span><strong>{context.round} · {context.type}</strong></div>
      <div><Gauge size={16} /><span>面试风格</span><strong>压力 {report.pressure_level} · 深度 {report.depth_level} · 引导 {report.guidance_level}</strong></div>
    </section>

    {partial && <div className="report-limitation"><AlertTriangle size={17} /><p><strong>有限证据报告</strong>这场面试中途结束，分数和建议不能代表完整岗位能力，请结合证据覆盖率和置信度阅读。</p></div>}

    <section className="report-key-findings">
      <div className="section-title"><div><h2>本场最重要的判断</h2><p>先看能够回到原回答的结论，再决定下一步训练</p></div><StatusBadge>{keyFindings.length} 项</StatusBadge></div>
      <div className="report-key-finding-list">{keyFindings.map((item, index) => {
        const score = report.content.skill_scores.find((entry) => entry.skill === item.skill);
        return <EvidenceChain key={`${item.skill}-${item.title}-${index}`} conclusion={item.title} evidence={item.evidence_quote} basis={item.analysis} confidence={score?.confidence} action={item.action} meta={`${item.skill} · 第 ${item.evidence_turns.join("、")} 轮`} tone={item.tone} />;
      })}</div>
    </section>

    {report.source_session_id && <RetrainingComparison report={report} sourceReport={sourceReport?.session_id === report.source_session_id ? sourceReport : null} error={sourceReportError?.sourceId === report.source_session_id ? sourceReportError.message : ""} />}

    <section className="report-overview">
      <div className="overall-score"><span>已覆盖回答表现</span><div><strong>{report.content.overall_score}</strong><small>/ 100</small></div><StatusBadge>{Math.round(report.content.confidence * 100)}% 置信度</StatusBadge><p>{report.content.summary}</p></div>
      <div className="score-breakdown"><div className="panel-heading"><div><span>能力分布</span><small>每项均引用回答轮次，可申请独立复核</small></div></div>{report.content.skill_scores.map((item, index) => {
        const review = latestReview(index);
        const displayedScore = review?.decision === "revised" && review.revised_score !== null && review.revised_score !== undefined ? review.revised_score : item.score;
        return <div className="score-row" key={`${item.skill}-${index}`}><div><span>{item.skill}</span><strong>{displayedScore}{displayedScore !== item.score && <small>原 {item.score}</small>}</strong></div><div className="score-track"><i style={{ width: `${displayedScore}%` }} /></div><div className="score-evidence-line"><small>证据：第 {item.evidence_turns.join("、")} 轮 · 置信度 {Math.round(item.confidence * 100)}%</small><button type="button" onClick={() => openReview({ skillIndex: index, skill: item.skill, originalScore: item.score })}><Scale size={13} />{review ? "再次处理" : "对此评分有异议"}</button></div>{review && <ReviewResult review={review} />}</div>;
      })}</div>
      <div className="report-strength"><CheckCircle2 size={21} /><div><span>有证据的优势</span><strong>{report.content.strengths.length ? `${report.content.strengths.length} 项表现得到回答证据支持` : "当前证据不足以确认明显优势"}</strong><p>{report.content.strengths.length ? report.content.strengths.map((item) => item.skill).join(" · ") : "完成更多问题后，系统才能形成更稳定的优势判断。"}</p></div></div>
    </section>

    <section className="report-evidence-section">
      <div className="section-title"><div><h2>有证据的优势</h2><p>只展示能够引用本场原回答的正向表现</p></div><StatusBadge tone="success">{report.content.strengths.length} 项</StatusBadge></div>
      {report.content.strengths.length ? <div className="report-strength-list">{report.content.strengths.map((item, index) => <EvidenceChain key={`${item.skill}-${index}`} conclusion={item.title} evidence={item.evidence_quote} basis={item.analysis} confidence={report.content.skill_scores.find((score) => score.skill === item.skill)?.confidence} action="在更高难度或新的追问情境中再次验证这一表现。" meta={`${item.skill} · 第 ${item.evidence_turns.join("、")} 轮`} tone="positive" />)}</div> : <div className="report-empty-evidence"><CheckCircle2 size={18} /><span>当前回答证据不足以形成稳定优势判断</span></div>}
    </section>

    <section className="report-timeline">
      <div className="section-title"><div><h2>逐轮问答回放</h2><p>按真实提交顺序查看问题、回答和面试官后续动作</p></div><StatusBadge>{report.turns.length} 轮</StatusBadge></div>
      <div className="report-turn-list">{report.turns.map((turn, index) => <details key={turn.sequence} open={index === 0}><summary><span className="turn-sequence">{String(turn.sequence).padStart(2, "0")}</span><div><small>{turn.phase_name} · 主问题 {turn.question_number}{turn.decision === "follow_up" ? " · 产生追问" : ""}</small><strong>{turn.question}</strong></div><span className="turn-mode">{turn.answer_mode === "voice" ? <AudioLines size={14} /> : <Keyboard size={14} />}{turn.answer_mode === "voice" ? "语音" : "文字"}</span></summary><div className="report-turn-content"><div><MessageSquareQuote size={16} /><section><span>你的回答</span><p>{turn.answer}</p></section></div><div><CheckCircle2 size={16} /><section><span>面试官后续</span><p>{[turn.transition, turn.interviewer_reply, turn.follow_up_question ?? (turn.decision === "next" ? "进入下一题。" : null)].filter(Boolean).join(" ")}</p></section></div></div></details>)}</div>
    </section>

    {report.board_snapshot && <ReportBoardPlayback snapshot={report.board_snapshot} />}
    {(report.coding_evidence ?? []).length > 0 && <ReportCodingEvidence evidence={report.coding_evidence ?? []} />}

    {(report.verification_status === "degraded" || report.verified_claims.length > 0) && <section className="report-verification-section"><div className="section-title"><div><h2>技术主张核验</h2><p>只使用已审核知识包，证据不足不会被定性为错误</p></div><StatusBadge tone={report.verification_status === "degraded" ? "warning" : "success"}>{report.verification_status === "degraded" ? "核验降级" : `${report.verified_claims.length} 条`}</StatusBadge></div>{report.verification_status === "degraded" ? <div className="verification-degraded"><AlertTriangle size={17} /><p><strong>本次事实核验未完成</strong>{report.verification_error || "权威知识检索暂时不可用，报告没有据此判断技术错误。"}</p></div> : <div className="verification-list">{report.verified_claims.map((claim, index) => <VerifiedClaimItem key={`${claim.sequence}-${index}`} claim={claim} />)}</div>}</section>}

    <div className="report-content">
      <section className="evidence-list"><div className="section-title"><div><h2>优先改进项</h2><p>选择要带入下一场弱项复训的内容</p></div><StatusBadge>{selectedImprovements.length} / {report.content.improvements.length} 已选</StatusBadge></div>{report.content.improvements.length ? report.content.improvements.map((item, index) => <EvidenceItem key={`${item.skill}-${index}`} item={item} confidence={report.content.skill_scores.find((score) => score.skill === item.skill)?.confidence} selected={selectedImprovements.includes(index)} onToggle={() => toggleImprovement(index)} />) : <div className="evidence-item"><h3>当前没有足够证据形成改进项</h3><p>继续完成更多面试问题后再生成完整报告。</p></div>}</section>
      <aside className="next-training"><Target size={22} /><span className="next-training-kicker">下一场训练</span><h2>建议这样练</h2><p>{report.content.next_training}</p><div className="retraining-selection"><strong>{selectedImprovements.length} 项改进内容</strong><span>{selectedImprovements.length ? "会与本场岗位和面试风格一起带回准备页" : "未选择具体改进项，将只使用整体训练建议"}</span></div><Button className="w-full" size="lg" type="button" onClick={startRetraining}>创建弱项复训</Button><div className="report-version"><span>模型 {report.model}</span><span>Prompt {report.prompt_version}</span><span>标准 {report.rubric_version}</span></div></aside>
    </div>
    <Dialog open={Boolean(reviewTarget)} onOpenChange={(open) => { if (!open && !reviewSubmitting) setReviewTarget(null); }}>
      {reviewTarget && <DialogContent aria-describedby="review-dialog-description">
        <DialogHeader className="review-dialog-heading"><Scale size={20} /><div><span>报告异议</span><DialogTitle>重新处理“{reviewTarget.skill}”评分</DialogTitle></div></DialogHeader>
        <DialogDescription id="review-dialog-description">原报告和回答证据会保留，处理结果将作为单独记录附在报告上。</DialogDescription>
        <div className="review-score-context"><span>报告原评分</span><strong>{reviewTarget.originalScore}</strong><p>提交后可在当前报告中查看处理状态与复核结论。</p></div>
        <fieldset className="review-action-selector"><legend>你希望如何处理</legend><label className={reviewAction === "reevaluate" ? "selected" : ""}><input type="radio" name="review-action" value="reevaluate" checked={reviewAction === "reevaluate"} onChange={() => setReviewAction("reevaluate")} /><span><strong>请求 AI 独立复核</strong><small>重新读取对应问题和回答，可能维持、修改或判定证据不足</small></span></label><label className={reviewAction === "exclude" ? "selected" : ""}><input type="radio" name="review-action" value="exclude" checked={reviewAction === "exclude"} onChange={() => setReviewAction("exclude")} /><span><strong>不计入能力画像</strong><small>立即从长期技能矩阵中排除，本场报告总分和原始记录不变</small></span></label></fieldset>
        <label className="review-reason"><span>异议理由</span><textarea value={reviewReason} onChange={(event) => setReviewReason(event.target.value.slice(0, 1_000))} placeholder="例如：回答中已经说明了个人职责和结果，但评分理由只提到了缺少指标……" rows={5} disabled={reviewSubmitting} /><small>{reviewReason.trim().length} / 1000，至少 10 个字</small></label>
        {reviewError && <div className="review-dialog-error" role="alert">{reviewError}</div>}
        <DialogFooter className="max-sm:flex-col-reverse"><Button type="button" variant="secondary" onClick={() => setReviewTarget(null)} disabled={reviewSubmitting}>取消</Button><Button type="button" onClick={() => void submitReview()} disabled={reviewSubmitting || reviewReason.trim().length < 10}>{reviewSubmitting && <LoaderCircle className="spin" size={15} />}{reviewSubmitting ? (reviewAction === "reevaluate" ? "正在复核" : "正在更新") : (reviewAction === "reevaluate" ? "提交并复核" : "确认排除")}</Button></DialogFooter>
      </DialogContent>}
    </Dialog>
  </main>;
}

function RetrainingComparison({
  report,
  sourceReport,
  error,
}: {
  report: InterviewReportData;
  sourceReport: InterviewReportData | null;
  error: string;
}) {
  if (error) return <section className="report-retraining-comparison"><div className="section-title"><div><h2>弱项复训验证</h2><p>来源关系已保留，但旧报告暂时无法读取</p></div></div><div className="report-limitation"><AlertTriangle size={17} /><p>{error}</p></div></section>;
  if (!sourceReport) return <section className="report-retraining-comparison"><AiWorkReceipt title="正在读取来源训练证据" description="本场是弱项复训，系统正在恢复上一场改进项用于前后核对。" activeStep={0} steps={[{ label: "正在读取已保存的来源报告", detail: "只比较已有证据，不会重新调用模型评分" }]} footer="来源报告不可用时会明确提示，不会生成替代结论。" /></section>;

  const comparisons = sourceReport.content.improvements.map((previous) => {
    const strength = report.content.strengths.find((item) => item.skill === previous.skill);
    const improvement = report.content.improvements.find((item) => item.skill === previous.skill);
    const current = strength ?? improvement;
    const score = report.content.skill_scores.find((item) => item.skill === previous.skill);
    if (strength) return { previous, current, score, title: "本场出现正向证据", basis: `来源报告将“${previous.title}”列为改进项；本场同一能力被报告识别为有证据的优势。`, tone: "positive" as const, action: "在新的题目或更高压力下再次验证，确认表现是否稳定。" };
    if (improvement) return { previous, current, score, title: "本场仍有同类改进证据", basis: `来源报告与本场报告都在“${previous.skill}”下发现改进证据，当前不能判定缺口已经关闭。`, tone: "warning" as const, action: improvement.improvement ?? report.content.next_training };
    return { previous, current: null, score, title: "本场未覆盖同一能力", basis: `来源报告的“${previous.skill}”改进项没有在本场优势或改进项中出现，不能据此判断已经改善。`, tone: "neutral" as const, action: "安排一次明确考察该能力的训练，补充可比较证据。" };
  });

  return <section className="report-retraining-comparison">
    <div className="section-title"><div><h2>弱项复训验证</h2><p>按相同能力名称对照来源报告与本场证据，不重新评分</p></div><Link href={`/report?session=${sourceReport.session_id}`} className="secondary-button">查看来源报告 <ArrowLeft size={14} /></Link></div>
    <div className="report-key-finding-list">{comparisons.map(({ previous, current, score, title, basis, tone, action }) => <EvidenceChain key={`${previous.skill}-${previous.title}`} conclusion={title} previousEvidence={previous.evidence_quote} evidence={current?.evidence_quote} basis={basis} confidence={score?.confidence} action={action} meta={`${previous.skill} · 来源改进项`} tone={tone} />)}</div>
  </section>;
}

function ReportBoardPlayback({ snapshot }: { snapshot: NonNullable<InterviewReportData["board_snapshot"]> }) {
  const nodeList = snapshot.state.nodes ?? [];
  const edgeList = snapshot.state.edges ?? [];
  const nodes = new Map(nodeList.map((node) => [node.id, node]));
  return <section className="report-board-section"><div className="section-title"><div><h2>系统设计白板回放</h2><p>报告生成时保存的最后一个结构化快照 · 第 {snapshot.revision + 1} 版</p></div><StatusBadge>只读</StatusBadge></div><div className="report-board-canvas"><svg aria-hidden="true">{edgeList.map((edge) => { const source = nodes.get(edge.source_id); const target = nodes.get(edge.target_id); if (!source || !target) return null; return <line key={edge.id} x1={source.x + source.width / 2} y1={source.y + source.height / 2} x2={target.x + target.width / 2} y2={target.y + target.height / 2} />; })}</svg>{nodeList.map((node) => <article key={node.id} style={{ left: node.x, top: node.y, width: node.width, minHeight: node.height }}><small>{node.kind}</small><strong>{node.label}</strong></article>)}</div></section>;
}

function ReportCodingEvidence({ evidence }: { evidence: NonNullable<InterviewReportData["coding_evidence"]> }) {
  return <section className="report-coding-section">
    <div className="section-title"><div><h2>Coding 过程回放</h2><p>报告生成时保存的代码、运行记录与复杂度说明</p></div><StatusBadge>{evidence.length} 道</StatusBadge></div>
    <div className="report-coding-list">{evidence.map((item) => {
      const runs = item.runs ?? [];
      const latestRun = runs[runs.length - 1];
      return <article key={`${item.phase_index}:${item.question_index}`}>
        <header><Code2 size={17} /><div><strong>{item.problem.title}</strong><span>{item.snapshot_count} 个代码版本 · {runs.length} 次运行</span></div>{latestRun && <StatusBadge tone={latestRun.status === "passed" ? "success" : "warning"}>{latestRun.passed_count} / {latestRun.total_count} 通过</StatusBadge>}</header>
        <pre><code>{item.latest_source}</code></pre>
        <div className="coding-report-notes"><strong>复杂度说明</strong><p>{item.complexity_notes || "本场没有提交复杂度说明。"}</p></div>
        {runs.length > 0 && <div className="coding-run-history">{runs.map((run, index) => <span key={`${run.created_at}-${index}`} className={run.status === "passed" ? "passed" : "failed"}>v{run.snapshot_revision + 1} · {run.passed_count}/{run.total_count} · {run.duration_ms}ms</span>)}</div>}
      </article>;
    })}</div>
  </section>;
}

function ReviewResult({ review }: { review: InterviewReportReviewData }) {
  const labels: Record<NonNullable<InterviewReportReviewData["decision"]>, string> = {
    upheld: "复核维持原评分",
    revised: `复核调整为 ${review.revised_score} 分`,
    uncertain: "复核认为证据不足，暂不计入画像",
    excluded: "已从长期能力画像排除",
  };
  const label = review.status === "failed"
    ? "上次处理未完成"
    : review.decision ? labels[review.decision] : "正在处理";
  return <div className={`score-review-result ${review.decision === "excluded" ? "excluded" : ""}`}><strong>{label}</strong>{review.rationale && <p>{review.rationale}</p>}{review.model && <small>{review.model} · {review.prompt_version}</small>}</div>;
}

function VerifiedClaimItem({
  claim,
}: {
  claim: InterviewReportData["verified_claims"][number];
}) {
  const labels = {
    supported: "证据支持",
    contradicted: "证据冲突",
    uncertain: "证据不足",
  } as const;
  const tone = claim.result === "supported" ? "success" : claim.result === "contradicted" ? "warning" : "neutral";
  return <article className={`verification-item ${claim.result}`}><div className="verification-item-heading"><BookOpenCheck size={17} /><div><span>第 {claim.sequence} 轮技术主张</span><h3>{claim.claim}</h3></div><StatusBadge tone={tone}>{labels[claim.result]} · {Math.round(claim.confidence * 100)}%</StatusBadge></div><blockquote><span>你的原话</span>“{claim.evidence_quote}”</blockquote><p>{claim.rationale}</p>{claim.citations?.length ? <div className="verification-citations"><strong>核验依据</strong>{claim.citations.map((citation) => <details key={citation.chunk_id}><summary>{citation.title}{citation.version ? ` · v${citation.version}` : ""}</summary><p>{citation.quote}</p>{citation.source_urls?.length ? <div>{citation.source_urls.map((url, index) => <a href={url} key={url} target="_blank" rel="noreferrer">参考来源 {index + 1}<ExternalLink size={12} /></a>)}</div> : <small>该知识包没有可公开跳转的来源链接</small>}</details>)}</div> : <small className="verification-no-citation">没有检索到足以形成明确结论的知识引用</small>}</article>;
}

function ReportProcessState({
  phase,
  message,
  elapsedSeconds,
}: {
  phase: "loading" | "generating";
  message: string;
  elapsedSeconds: number;
}) {
  const generating = phase === "generating";
  return <main className="content-container report-process-page"><AiWorkReceipt title={generating ? "正在生成本次面试报告" : "正在确认报告状态"} description={message} activeStep={0} steps={[{ label: generating ? "报告任务正在后台运行" : "正在读取已保存的报告状态", detail: "完成后会保留回答证据、评分版本和置信度" }]} footer={generating ? `已等待 ${elapsedSeconds} 秒，离开页面后任务仍可从训练记录恢复。` : "只读取已保存的训练状态，不会重复生成报告。"} /></main>;
}

function EvidenceItem({
  item,
  confidence,
  selected,
  onToggle,
}: {
  item: InterviewReportData["content"]["improvements"][number];
  confidence?: number;
  selected: boolean;
  onToggle: () => void;
}) {
  return <EvidenceChain conclusion={item.title} evidence={item.evidence_quote} basis={item.analysis} confidence={confidence} action={item.improvement ?? "补充能够验证结论的具体过程和数据。"} meta={`${item.skill} · 第 ${item.evidence_turns.join("、")} 轮证据`} tone="warning" controls={<button className="evidence-retrain-toggle" type="button" aria-pressed={selected} onClick={onToggle}>{selected ? <Check size={14} /> : <Plus size={14} />}{selected ? "已加入复训" : "加入复训"}</button>} />;
}
