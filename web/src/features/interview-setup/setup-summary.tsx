import { ArrowRight, Check, FileText, Mic2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentParseStatus, INTERVIEW_TYPE_OPTIONS, LEVEL_OPTIONS, MODE_OPTIONS, ROUND_OPTIONS, SetupState } from "./model";

export function SetupSummary({ state, readiness, parseStatus, onContinue, saving, saveError }: { state: SetupState; readiness: number; parseStatus: DocumentParseStatus; onContinue: () => void; saving?: boolean; saveError?: string }) {
  const modeLabel = MODE_OPTIONS.find((item) => item.value === state.mode)?.label;
  const levelLabel = LEVEL_OPTIONS.find((item) => item.value === state.level)?.label;
  const roundLabel = ROUND_OPTIONS.find((item) => item.value === state.interviewRound)?.label;
  const typeLabel = INTERVIEW_TYPE_OPTIONS.find((item) => item.value === state.interviewType)?.label;
  const canContinue = readiness === 100 && parseStatus === "success";

  return (
    <aside className="lg:sticky lg:top-8 lg:self-start">
      <div className="summary-panel">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">本次训练</h2>
          <span className="status-dot">配置中</span>
        </div>
        <div className="readiness">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-xs text-[var(--muted)]">材料完整度</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">{readiness}%</p>
            </div>
            <Sparkles size={20} className="text-[var(--accent)]" />
          </div>
          <div className="mt-4 h-1.5 overflow-hidden bg-[var(--soft)]">
            <div className="h-full bg-[var(--accent)] transition-all" style={{ width: `${readiness}%` }} />
          </div>
        </div>
        <dl className="summary-list">
          <div><dt>岗位</dt><dd>{state.role || "待填写"}</dd></div>
          <div><dt>目标公司</dt><dd>{state.company || "不指定公司"}</dd></div>
          <div><dt>目标场次</dt><dd>{levelLabel} · {roundLabel}</dd></div>
          <div><dt>训练类型</dt><dd>{typeLabel}</dd></div>
          <div><dt>模式与时长</dt><dd>{modeLabel} · {state.duration} 分钟</dd></div>
          <div><dt>面试风格</dt><dd>压力 {state.pressure} · 深度 {state.depth} · 引导 {state.guidance}</dd></div>
          <div><dt>题库重点</dt><dd>{state.selectedQuestions.length ? `${state.selectedQuestions.length} 道已选题目` : "按简历与 JD 生成"}</dd></div>
          <div><dt>复训重点</dt><dd>{state.trainingFocus || "综合训练"}</dd></div>
          <div><dt>输入方式</dt><dd className="flex items-center gap-1.5"><FileText size={14} />实时语音 / 文字备用</dd></div>
        </dl>
        <div className="check-list">
          <CheckItem done={parseStatus === "success"}>简历已真实解析</CheckItem>
          <CheckItem done={state.jd.trim().length >= 30}>JD 内容可供分析</CheckItem>
          <CheckItem done={Boolean(state.role.trim())}>已确定目标岗位</CheckItem>
        </div>
        {saveError && <p className="setup-save-error" role="alert">{saveError}</p>}
        <Button className="mt-4 w-full" size="lg" type="button" onClick={canContinue ? onContinue : undefined} disabled={!canContinue || saving}>
          {saving ? "正在保存训练草稿" : parseStatus === "parsing" ? "正在解析简历" : canContinue ? "进入材料校正" : "完成材料后继续"}
          <ArrowRight size={17} />
        </Button>
        <p className="mt-3 text-center text-[12px] leading-5 text-[var(--muted)]">
          下一步可以检查技能提取结果，并调整本次考察重点
        </p>
      </div>
      <div className="mt-4 flex items-start gap-3 border border-[var(--line)] bg-white p-4 text-xs leading-5 text-[var(--muted)]">
        <Mic2 size={17} className="mt-0.5 shrink-0 text-[var(--ink)]" />
        <p>语音面试已接入实时听写。压力等级 4 以上时，面试官可能在明显跑题、重复或长期空泛时礼貌打断。</p>
      </div>
    </aside>
  );
}

function CheckItem({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`check-icon ${done ? "check-icon-done" : ""}`}>
        {done && <Check size={11} strokeWidth={3} />}
      </span>
      <span className={done ? "text-[var(--ink)]" : ""}>{children}</span>
    </div>
  );
}
