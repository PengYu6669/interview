import {
  BriefcaseBusiness,
  Building2,
  ChevronDown,
  Clock3,
  Milestone,
  Settings2,
  Target,
} from "lucide-react";

import {
  DURATION_OPTIONS,
  INTERVIEW_TYPE_OPTIONS,
  InterviewMode,
  InterviewRound,
  InterviewType,
  LEVEL_OPTIONS,
  MODE_OPTIONS,
  ROUND_OPTIONS,
  TargetLevel,
} from "./model";
import { SectionHeading } from "./section-heading";

interface TargetSectionProps {
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
  trainingFocus: string;
  onRoleChange: (value: string) => void;
  onCompanyChange: (value: string) => void;
  onLevelChange: (value: TargetLevel) => void;
  onInterviewRoundChange: (value: InterviewRound) => void;
  onInterviewTypeChange: (value: InterviewType) => void;
  onModeChange: (value: InterviewMode) => void;
  onDurationChange: (value: number) => void;
  onPressureChange: (value: number) => void;
  onDepthChange: (value: number) => void;
  onGuidanceChange: (value: number) => void;
  onTrainingFocusChange: (value: string) => void;
}

export function TargetSection(props: TargetSectionProps) {
  const typeLabel = INTERVIEW_TYPE_OPTIONS.find((item) => item.value === props.interviewType)?.label ?? "综合模拟";
  const modeLabel = MODE_OPTIONS.find((item) => item.value === props.mode)?.label ?? "标准模式";
  return (
    <section className="form-section" aria-labelledby="target-title">
      <SectionHeading
        index="02"
        title="目标与场次"
        description="这些信息会真实进入面试计划，决定覆盖范围、难度和轮次侧重"
        titleId="target-title"
      />

      <div className="target-context-essential">
        <ContextInput
          id="role"
          label="目标岗位"
          icon={<BriefcaseBusiness size={17} />}
          value={props.role}
          maxLength={150}
          placeholder="例如：Java 后端工程师"
          onChange={props.onRoleChange}
        />
      </div>

      <div className="setup-duration-row">
        <div><span className="field-label">预计时长</span><div className="duration-control"><Clock3 size={17} />{DURATION_OPTIONS.map((minutes) => <button key={minutes} type="button" className={props.duration === minutes ? "duration-active" : ""} onClick={() => props.onDurationChange(minutes)}>{minutes} 分钟</button>)}</div></div>
      </div>

      <details className="setup-advanced">
        <summary><div><strong>调整训练方式与面试强度</strong><span>{typeLabel} · {modeLabel} · {props.duration} 分钟</span></div><ChevronDown size={17} /></summary>
        <div className="setup-advanced-body">
        <div className="target-context-grid">
        <ContextInput
          id="company"
          label="目标公司（可选）"
          icon={<Building2 size={17} />}
          value={props.company}
          maxLength={100}
          placeholder="例如：某互联网公司"
          onChange={props.onCompanyChange}
        />
        <ContextSelect
          id="level"
          label="目标职级"
          icon={<Settings2 size={17} />}
          value={props.level}
          options={LEVEL_OPTIONS}
          onChange={(value) => props.onLevelChange(value as TargetLevel)}
        />
        <ContextSelect
          id="round"
          label="面试轮次"
          icon={<Milestone size={17} />}
          value={props.interviewRound}
          options={ROUND_OPTIONS}
          onChange={(value) => props.onInterviewRoundChange(value as InterviewRound)}
        />
        </div>

      <div className="setup-subsection">
        <div className="setup-subsection-title"><Target size={16} /><div><strong>本次训练类型</strong><span>决定主要考察范围，具体问题仍由材料和 JD 生成</span></div></div>
        <div className="training-type-grid">
          {INTERVIEW_TYPE_OPTIONS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`training-type-option ${props.interviewType === item.value ? "active" : ""}`}
              onClick={() => props.onInterviewTypeChange(item.value)}
              aria-pressed={props.interviewType === item.value}
            >
              <strong>{item.label}</strong><span>{item.description}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="setup-subsection">
        <div className="setup-subsection-title"><Settings2 size={16} /><div><strong>面试官风格</strong><span>选择预设后仍可微调三个独立维度</span></div></div>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODE_OPTIONS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`choice-button ${props.mode === item.value ? "choice-button-active" : ""}`}
              onClick={() => props.onModeChange(item.value)}
              aria-pressed={props.mode === item.value}
            >
              <span className="text-sm font-semibold">{item.label}</span>
              <span className="mt-1 block text-xs text-[var(--muted)]">{item.description}</span>
            </button>
          ))}
        </div>
        <details className="style-tuning">
          <summary><span>行为参数微调</span><small>压力 {props.pressure} · 深度 {props.depth} · 引导 {props.guidance}</small><ChevronDown size={15} /></summary>
          <div className="interview-style-controls">
            <StyleLevel label="压力程度" value={props.pressure} low="耐心" high="强势追问" onChange={props.onPressureChange} />
            <StyleLevel label="技术深度" value={props.depth} low="基础概念" high="边界与取舍" onChange={props.onDepthChange} />
            <StyleLevel label="引导程度" value={props.guidance} low="独立作答" high="逐步引导" onChange={props.onGuidanceChange} />
          </div>
        </details>
      </div>

      <label className="training-focus-field"><span className="field-label">本次复训重点（可选）</span><textarea value={props.trainingFocus} maxLength={500} onChange={(event) => props.onTrainingFocusChange(event.target.value)} placeholder="例如：项目贡献讲得太泛，需要补充个人职责、量化结果和技术取舍" /><small>{props.trainingFocus.length} / 500</small></label>
        </div>
      </details>
    </section>
  );
}

function ContextInput({ id, label, icon, value, maxLength, placeholder, onChange }: { id: string; label: string; icon: React.ReactNode; value: string; maxLength: number; placeholder?: string; onChange: (value: string) => void }) {
  return <div><label className="field-label" htmlFor={id}>{label}</label><div className="input-shell">{icon}<input id={id} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></div></div>;
}

function ContextSelect({ id, label, icon, value, options, onChange }: { id: string; label: string; icon: React.ReactNode; value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void }) {
  return <div><label className="field-label" htmlFor={id}>{label}</label><div className="input-shell">{icon}<select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={15} /></div></div>;
}

function StyleLevel({ label, value, low, high, onChange }: { label: string; value: number; low: string; high: string; onChange: (value: number) => void }) {
  return <label className="style-level"><span><strong>{label}</strong><b>{value} / 5</b></span><input type="range" min="1" max="5" step="1" value={value} onChange={(event) => onChange(Number(event.target.value))} /><small><i>{low}</i><i>{high}</i></small></label>;
}
