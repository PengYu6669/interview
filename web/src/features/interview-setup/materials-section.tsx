import { Upload } from "lucide-react";
import { DragEvent, RefObject, useState } from "react";

import { SectionHeading } from "./section-heading";
import { DocumentParseStatus } from "./model";

interface MaterialsSectionProps {
  resumeName: string;
  jd: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onFileSelected: (file: File) => void;
  onJdChange: (value: string) => void;
  parseStatus: DocumentParseStatus;
  parseError: string;
}

export function MaterialsSection({
  resumeName,
  jd,
  fileInputRef,
  onFileSelected,
  onJdChange,
  parseStatus,
  parseError,
}: MaterialsSectionProps) {
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onFileSelected(file);
  }

  return (
    <section className="form-section" aria-labelledby="materials-title">
      <SectionHeading
        index="01"
        title="训练材料"
        titleId="materials-title"
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="resume-file">个人简历</label>
          <input
            ref={fileInputRef}
            id="resume-file"
            className="sr-only"
            type="file"
            accept=".pdf,.docx,.md,.txt"
            onChange={(event) => { const file = event.target.files?.[0]; if (file) onFileSelected(file); }}
          />
          <button
            type="button"
            className={`upload-zone ${dragging ? "upload-zone-dragging" : ""}`}
            onClick={() => fileInputRef.current?.click()}
            onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <span className="upload-icon"><Upload size={20} /></span>
            {resumeName ? (
              <span className="min-w-0 text-left">
                <span className="block truncate text-sm font-medium">{resumeName}</span>
                <span className={`mt-1 block text-xs ${parseStatus === "error" ? "text-[var(--danger)]" : "text-[var(--success)]"}`}>
                  {parseStatus === "parsing" ? "正在安全解析…" : parseStatus === "success" ? "解析成功，可重新上传" : parseError || "等待解析"}
                </span>
              </span>
            ) : (
              <span className="text-left">
                <span className="block text-sm font-medium">拖放简历到这里，或点击选择</span>
                <span className="mt-1 block text-xs text-[var(--muted)]">PDF、DOCX、Markdown 或 TXT · 最大 20MB</span>
              </span>
            )}
          </button>
          {parseError && <p className="mt-2 text-xs text-[var(--danger)]" role="alert">{parseError}</p>}
        </div>
        <div>
          <label className="field-label" htmlFor="jd">岗位描述（JD）· 至少 30 字</label>
          <textarea
            id="jd"
            value={jd}
            onChange={(event) => onJdChange(event.target.value)}
            className="text-area"
            placeholder="粘贴岗位职责、任职要求和加分项…"
          />
          <div className="mt-2 flex justify-between text-xs text-[var(--muted)]">
            <span>{jd.trim().length >= 30 ? "内容长度足够分析" : "建议至少提供 30 个字"}</span>
            <span>{jd.length} 字</span>
          </div>
        </div>
      </div>
    </section>
  );
}
