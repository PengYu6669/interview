import { AlertTriangle, FileText, Trash2 } from "lucide-react";

import { ResumeExtractionResult } from "@/lib/resume-extraction";

export function StructuredProfile({
  result,
  onChange,
}: {
  result: ResumeExtractionResult;
  onChange: (result: ResumeExtractionResult) => void;
}) {
  const profile = result.profile;
  const skills = profile.skills ?? [];
  const projects = profile.projects ?? [];

  return (
    <div className="review-fields">
      <section className="review-block">
        <div className="review-block-title"><div><h2>候选人摘要</h2><p>可直接修正，系统不会覆盖你的修改</p></div></div>
        <div className="review-block-content">
          <textarea
            className="answer-box"
            value={profile.summary ?? ""}
            onChange={(event) => onChange({ ...result, profile: { ...profile, summary: event.target.value } })}
            aria-label="候选人摘要"
          />
        </div>
      </section>

      <section className="review-block">
        <div className="review-block-title"><div><h2>技术栈</h2><p>每项都必须能回到简历原文</p></div></div>
        <div className="review-block-content">
          {skills.length ? skills.map((skill) => (
            <div className="editable-row" key={`${skill.value}-${skill.evidence}`}>
              <div><input className="editable-inline-input" aria-label="技能名称" value={skill.value} onChange={(event) => onChange({ ...result, profile: { ...profile, skills: skills.map((item) => item === skill ? { ...item, value: event.target.value } : item) } })} /><p>简历内容：{skill.evidence}</p></div>
              <button type="button" className="icon-action" aria-label={`删除 ${skill.value}`} onClick={() => onChange({ ...result, profile: { ...profile, skills: skills.filter((item) => item !== skill) } })}><Trash2 size={15} /></button>
            </div>
          )) : <p className="text-xs text-[var(--muted)]">没有从原文中提取到可验证技能。</p>}
        </div>
      </section>

      <section className="review-block">
        <div className="review-block-title"><div><h2>项目经历</h2><p>仅保留简历中能确认的项目</p></div></div>
        <div className="review-block-content">
          {projects.length ? projects.map((project) => (
            <article className="editable-row" key={`${project.name}-${project.evidence}`}>
              <div><input className="editable-inline-input" aria-label="项目名称" value={project.name} onChange={(event) => onChange({ ...result, profile: { ...profile, projects: projects.map((item) => item === project ? { ...item, name: event.target.value } : item) } })} /><textarea className="editable-inline-textarea" aria-label={`${project.name} 项目描述`} value={project.description} onChange={(event) => onChange({ ...result, profile: { ...profile, projects: projects.map((item) => item === project ? { ...item, description: event.target.value } : item) } })} /><p>简历内容：{project.evidence}</p></div><button type="button" className="icon-action" aria-label={`删除 ${project.name}`} onClick={() => onChange({ ...result, profile: { ...profile, projects: projects.filter((item) => item !== project) } })}><Trash2 size={15} /></button>
            </article>
          )) : <p className="text-xs text-[var(--muted)]">没有提取到可确认的项目经历。</p>}
        </div>
      </section>

      {(profile.warnings ?? []).length > 0 && (
        <section className="review-block">
          <div className="review-block-title"><div><h2>需要人工确认</h2><p>模型没有自行补全这些内容</p></div></div>
          <div className="review-block-content">
            {(profile.warnings ?? []).map((warning) => <p className="flex gap-2 text-xs text-[var(--warning)]" key={warning}><AlertTriangle size={14} />{warning}</p>)}
          </div>
        </section>
      )}

      <p className="flex items-center gap-2 text-[12px] text-[var(--muted)]"><FileText size={13} />模型 {result.model} · Prompt {result.prompt_version} · Schema {profile.schema_version}</p>
    </div>
  );
}
