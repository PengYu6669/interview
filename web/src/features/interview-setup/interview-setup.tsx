"use client";

import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { MaterialsSection } from "./materials-section";
import { InterviewMode } from "./model";
import { SetupSummary } from "./setup-summary";
import { SetupIntro } from "./setup-intro";
import { TargetSection } from "./target-section";
import { InterviewFlowProgress } from "@/features/interview-flow/flow-progress";
import { DraftRecovery } from "./draft-recovery";
import { useSetupState } from "./use-setup-state";

export function InterviewSetup({ careerPlanItemId }: { careerPlanItemId?: string }) {
  const {
    state,
    parseStatus,
    parseError,
    saveError,
    saving,
    sourceSessionId,
    readiness,
    fileInputRef,
    update,
    handleFile,
    resumeDraft,
    continueToReview,
  } = useSetupState(careerPlanItemId);

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader active="new" />
      <main className="setup-page">
        <SetupIntro />
        <DraftRecovery onResume={resumeDraft} />
        <InterviewFlowProgress current={1} />
        {sourceSessionId && (
          <section className="retraining-brief">
            <div>
              <span>弱项复训</span>
              <h2>这一次不是重新做题，而是验证上次缺口</h2>
              <p>{state.trainingFocus}</p>
            </div>
            <Link href={`/report?session=${sourceSessionId}`}>查看上次复盘</Link>
          </section>
        )}
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
                onModeChange={(value: InterviewMode) => update("mode", value)}
                onDurationChange={(value) => update("duration", value)}
                onPressureChange={(value) => update("pressure", value)}
                onDepthChange={(value) => update("depth", value)}
                onGuidanceChange={(value) => update("guidance", value)}
                onTrainingFocusChange={(value) => update("trainingFocus", value)}
              />
            </div>
          </section>
          <SetupSummary
            state={state}
            readiness={readiness}
            parseStatus={parseStatus}
            onContinue={continueToReview}
            saving={saving}
            saveError={saveError}
          />
        </div>
      </main>
    </div>
  );
}
