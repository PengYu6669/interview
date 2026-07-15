import { z } from "zod";

const nodeKindSchema = z.enum(["client", "gateway", "service", "database", "cache", "queue", "external", "text"]);
const annotationKindSchema = z.enum(["capacity", "note"]);

export const boardNodeSchema = z.object({
  id: z.string().uuid(),
  kind: nodeKindSchema,
  label: z.string().min(1).max(80),
  x: z.number().int().min(0).max(1080),
  y: z.number().int().min(0).max(540),
  width: z.number().int().min(120).max(320),
  height: z.number().int().min(56).max(180),
});

export const boardStateSchema = z.object({
  nodes: z.array(boardNodeSchema).max(40),
  edges: z.array(z.object({ id: z.string().uuid(), source_id: z.string().uuid(), target_id: z.string().uuid(), label: z.string().max(80) })).max(80),
  annotations: z.array(z.object({ id: z.string().uuid(), kind: annotationKindSchema, text: z.string().min(1).max(240), x: z.number().int().min(0).max(1100), y: z.number().int().min(0).max(600) })).max(40),
}).superRefine((value, ctx) => {
  const ids = new Set(value.nodes.map((node) => node.id));
  for (const edge of value.edges) {
    if (!ids.has(edge.source_id) || !ids.has(edge.target_id) || edge.source_id === edge.target_id) {
      ctx.addIssue({ code: "custom", message: "连线必须连接两个不同的现有组件", path: ["edges"] });
    }
  }
});

export const boardSnapshotSchema = z.object({
  id: z.string().uuid(),
  session_id: z.string().uuid(),
  revision: z.number().int().nonnegative(),
  client_snapshot_id: z.string().uuid(),
  state: boardStateSchema,
  created_at: z.string(),
});

export type BoardState = z.infer<typeof boardStateSchema>;
export type BoardSnapshot = z.infer<typeof boardSnapshotSchema>;

