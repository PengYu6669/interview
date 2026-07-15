import { CheckCircle2, LoaderCircle, RefreshCw, WifiOff } from "lucide-react";

export type InterviewConnectionState =
  | "online"
  | "offline"
  | "recovering"
  | "unavailable"
  | "restored";

export function ConnectionBanner({
  state,
  hasDraft,
  onRetry,
}: {
  state: InterviewConnectionState;
  hasDraft: boolean;
  onRetry: () => void;
}) {
  if (state === "online") return null;
  const recovering = state === "recovering";
  const restored = state === "restored";
  return <div className={`room-connection-banner ${state}`} role="status" aria-live="polite">
    {recovering ? <LoaderCircle className="spin" size={16} /> : restored ? <CheckCircle2 size={16} /> : <WifiOff size={16} />}
    <div>
      <strong>{recovering ? "正在恢复面试连接" : restored ? "连接已恢复" : state === "offline" ? "网络连接已断开" : "面试服务暂时不可用"}</strong>
      <span>{restored ? (hasDraft ? "本轮回答草稿仍在，请确认后继续提交。" : "面试进度已与服务端同步。") : hasDraft ? "本轮回答草稿已保留，不会自动重复提交。" : "计时仍以服务端为准，恢复后会自动同步进度。"}</span>
    </div>
    {!recovering && !restored && <button type="button" onClick={onRetry}><RefreshCw size={14} />重新连接</button>}
  </div>;
}
