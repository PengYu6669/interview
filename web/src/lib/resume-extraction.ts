import type { components } from "./api-schema";
import { z } from "zod";

export type ResumeExtractionResult = components["schemas"]["ResumeExtractionResult"];

const evidenceItemSchema = z.object({
  value: z.string().min(1),
  evidence: z.string().min(1),
});

const projectMetricSchema = z.object({
  name: z.string().min(1),
  value: z.string().min(1),
  evidence: z.string().min(1),
});

const resumeProjectSchema = z.object({
  name: z.string().min(1),
  role: z.string().nullable().optional(),
  description: z.string().min(1),
  technologies: z.array(evidenceItemSchema).optional(),
  metrics: z.array(projectMetricSchema).optional(),
  evidence: z.string().min(1),
});

const workExperienceSchema = z.object({
  organization: z.string().min(1),
  role: z.string().min(1),
  period: z.string().nullable().optional(),
  highlights: z.array(evidenceItemSchema).optional(),
  evidence: z.string().min(1),
});

const educationSchema = z.object({
  institution: z.string().min(1),
  major: z.string().nullable().optional(),
  degree: z.string().nullable().optional(),
  period: z.string().nullable().optional(),
  evidence: z.string().min(1),
});

export const resumeExtractionResultSchema: z.ZodType<ResumeExtractionResult> = z.object({
  profile: z.object({
    schema_version: z.string(),
    target_role: z.string().min(1),
    summary: z.string(),
    skills: z.array(evidenceItemSchema).optional(),
    projects: z.array(resumeProjectSchema).optional(),
    work_experiences: z.array(workExperienceSchema).optional(),
    education: z.array(educationSchema).optional(),
    jd_requirements: z.array(evidenceItemSchema).optional(),
    warnings: z.array(z.string()).optional(),
  }),
  model: z.string().min(1),
  prompt_version: z.string().min(1),
});

export const RESUME_EXTRACTION_STORAGE_KEY = "interview-copilot.resume-extraction.v1";

const CACHE_VERSION = "resume-extraction-cache-v2";

export const resumeExtractionCacheSchema = z.object({
  fingerprint: z.string().min(1),
  result: resumeExtractionResultSchema,
});

export async function resumeExtractionFingerprint(input: {
  resumeText: string;
  jd: string;
  targetRole: string;
}) {
  const source = `${CACHE_VERSION}\u0000${input.resumeText}\u0000${input.jd}\u0000${input.targetRole}`;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
