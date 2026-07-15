"use client";

import { Link2, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { boardSnapshotSchema, type BoardState } from "@/lib/interview-board";

const kinds = ["client", "gateway", "service", "database", "cache", "queue", "external", "text"] as const;

function emptyState(): BoardState { return { nodes: [], edges: [], annotations: [] }; }

export function SystemDesignBoard({ sessionId, readOnly = false }: { sessionId: string; readOnly?: boolean }) {
  const [state, setState] = useState<BoardState>(emptyState);
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState("正在读取白板");
  const [selected, setSelected] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [pendingEdge, setPendingEdge] = useState<string | null>(null);
  const [clientSnapshotId, setClientSnapshotId] = useState(crypto.randomUUID());
  const [dirty, setDirty] = useState(false);
  const nodeMap = useMemo(() => new Map(state.nodes.map((node) => [node.id, node])), [state.nodes]);

  useEffect(() => {
    let active = true;
    void fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/board`, { cache: "no-store" })
      .then((response) => response.json().then((payload) => ({ response, payload })))
      .then(({ response, payload }) => {
        if (!active) return;
        const parsed = response.ok && payload ? boardSnapshotSchema.safeParse(payload) : null;
        if (parsed?.success) { setState(parsed.data.state); setRevision(parsed.data.revision + 1); setDirty(false); setStatus("白板已加载"); }
        else if (response.status === 404) setStatus("尚未创建白板");
        else setStatus("白板暂时无法读取");
      })
      .catch(() => { if (active) setStatus("白板暂时无法读取"); });
    return () => { active = false; };
  }, [sessionId]);

  useEffect(() => {
    if (readOnly || !dirty || status === "正在读取白板") return;
    const timer = window.setTimeout(() => {
      void fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/board`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_snapshot_id: clientSnapshotId, base_revision: revision, state }) })
        .then(async (response) => {
          const payload: unknown = await response.json();
          if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "白板保存失败");
          const parsed = boardSnapshotSchema.safeParse(payload);
          if (!parsed.success) throw new Error("白板服务返回了无效数据");
          setRevision(parsed.data.revision + 1); setClientSnapshotId(crypto.randomUUID()); setDirty(false); setStatus("已自动保存");
        }).catch((error: unknown) => setStatus(error instanceof Error ? error.message : "白板保存失败"));
    }, 900);
    return () => window.clearTimeout(timer);
  }, [clientSnapshotId, dirty, readOnly, revision, sessionId, state, status]);

  function addNode() {
    const id = crypto.randomUUID();
    setState((current) => ({ ...current, nodes: [...current.nodes, { id, kind: "service", label: "新组件", x: 80 + current.nodes.length * 18, y: 80 + current.nodes.length * 14, width: 180, height: 72 }] }));
    setDirty(true);
    setSelected(id);
  }
  function removeSelected() {
    if (!selected) return;
    setState((current) => ({ ...current, nodes: current.nodes.filter((node) => node.id !== selected), edges: current.edges.filter((edge) => edge.source_id !== selected && edge.target_id !== selected), annotations: current.annotations.filter((item) => item.id !== selected) }));
    setDirty(true);
    setSelected(null);
  }
  function selectNode(id: string) {
    if (pendingEdge && pendingEdge !== id) {
      setState((current) => ({ ...current, edges: [...current.edges, { id: crypto.randomUUID(), source_id: pendingEdge, target_id: id, label: "请求" }] }));
      setDirty(true);
      setPendingEdge(null);
    } else setSelected(id);
  }
  return <section className="system-design-board" aria-label="系统设计白板">
    <header><div><strong>系统设计白板</strong><span>{status}</span></div>{!readOnly && <div className="board-actions"><button type="button" onClick={addNode}><Plus size={14} />添加组件</button><button type="button" onClick={() => selected && setPendingEdge(selected)} disabled={!selected}><Link2 size={14} />连接组件</button><button type="button" onClick={removeSelected} disabled={!selected}><Trash2 size={14} />删除</button><Save size={15} aria-label="自动保存" /></div>}</header>
    <div className="board-canvas" onPointerMove={(event) => { if (!dragging || readOnly) return; const rect = event.currentTarget.getBoundingClientRect(); const x = Math.max(0, Math.round(event.clientX - rect.left - dragging.dx)); const y = Math.max(0, Math.round(event.clientY - rect.top - dragging.dy)); setDirty(true); setState((current) => ({ ...current, nodes: current.nodes.map((node) => node.id === dragging.id ? { ...node, x, y } : node) })); }} onPointerUp={() => setDragging(null)}>
      <svg className="board-lines" aria-hidden="true">{state.edges.map((edge) => { const source = nodeMap.get(edge.source_id); const target = nodeMap.get(edge.target_id); if (!source || !target) return null; return <line key={edge.id} x1={source.x + source.width / 2} y1={source.y + source.height / 2} x2={target.x + target.width / 2} y2={target.y + target.height / 2} />; })}</svg>
      {state.nodes.map((node) => <article key={node.id} className={`board-node ${selected === node.id ? "selected" : ""}`} style={{ left: node.x, top: node.y, width: node.width, minHeight: node.height }} onClick={() => selectNode(node.id)} onPointerDown={(event) => { if (readOnly) return; const rect = event.currentTarget.getBoundingClientRect(); setDragging({ id: node.id, dx: event.clientX - rect.left, dy: event.clientY - rect.top }); }}><small>{node.kind}</small>{readOnly ? <strong>{node.label}</strong> : <input value={node.label} onChange={(event) => { setDirty(true); setState((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === node.id ? { ...item, label: event.target.value } : item) })); }} onClick={(event) => event.stopPropagation()} />}</article>)}
      {state.nodes.length === 0 && <div className="board-empty"><strong>从一个组件开始设计</strong><span>添加客户端、服务、数据库，再连接它们的数据流。</span>{!readOnly && <button type="button" onClick={addNode}><Plus size={14} />添加第一个组件</button>}</div>}
    </div>
    <footer>组件类型：{kinds.join(" · ")} {pendingEdge && " · 再点击一个组件完成连线"}</footer>
  </section>;
}
