"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import {
  CoachingSession,
  coachingSessionSchema,
} from "@/lib/coaching";
import { useVoiceTranscription } from "./use-voice-transcription";

export function useCoachingSession(sessionId: string) {
  const [session, setSession] = useState<CoachingSession | null>(null);
  const [answer, setAnswer] = useState("");
  const [answerMode, setAnswerMode] = useState<"text" | "voice">("text");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [puzzleAssignments, setPuzzleAssignments] = useState<Record<string, string>>({});
  const [puzzleComplete, setPuzzleComplete] = useState(false);
  const [puzzleError, setPuzzleError] = useState("");
  const attemptStartedAt = useRef(0);

  const voice = useVoiceTranscription(sessionId, (text) => {
    setAnswer(text);
    setAnswerMode("voice");
  });

  const applySession = useCallback((data: CoachingSession) => {
    setSession(data);
    setRemaining(data.task.time_limit_seconds);
    setPuzzleComplete(data.turns.length > 0 || !data.task.puzzle);
    attemptStartedAt.current = Date.now();
  }, []);

  const fetchSession = useCallback(async () => {
    return apiGet(`/api/coaching-sessions/${sessionId}`, coachingSessionSchema);
  }, [sessionId]);

  useEffect(() => {
    let mounted = true;
    void fetchSession()
      .then((data) => {
        if (mounted) applySession(data);
      })
      .catch((cause: unknown) => {
        if (mounted) setError(cause instanceof ApiError ? cause.message : "训练读取失败");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [applySession, fetchSession]);

  useEffect(() => {
    if (!session || session.status !== "active" || !puzzleComplete) return;
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1_000);
    return () => window.clearInterval(timer);
  }, [puzzleComplete, session]);

  async function reload() {
    setLoading(true);
    setError("");
    try {
      applySession(await fetchSession());
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "训练读取失败");
    } finally {
      setLoading(false);
    }
  }

  async function start() {
    setSubmitting(true);
    setError("");
    try {
      const data = await apiPost(`/api/coaching-sessions/${sessionId}/start`, {}, coachingSessionSchema);
      applySession(data);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "训练暂时无法开始");
    } finally {
      setSubmitting(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!answer.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const elapsedSeconds = Math.min(3_600, Math.max(0, Math.round((Date.now() - attemptStartedAt.current) / 1_000)));
      const messageId = crypto.randomUUID();
      const data = await apiPost(
        `/api/coaching-sessions/${sessionId}/answers`,
        { client_message_id: messageId, answer: answer.trim(), answer_mode: answerMode, elapsed_seconds: elapsedSeconds },
        coachingSessionSchema,
      );
      applySession(data);
      setAnswer("");
      setAnswerMode("text");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "回答提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  function checkPuzzle() {
    const fragments = session?.task.puzzle?.fragments ?? [];
    const incorrect = fragments.some((item) => puzzleAssignments[item.id] !== item.target_key);
    if (incorrect) {
      setPuzzleError("还有片段位置不准确，按表达顺序再检查一次。");
      return;
    }
    setPuzzleError("");
    setPuzzleComplete(true);
    setRemaining(session?.task.time_limit_seconds ?? 0);
    attemptStartedAt.current = Date.now();
  }

  return {
    session,
    answer,
    setAnswer,
    answerMode,
    setAnswerMode,
    loading,
    submitting,
    error,
    remaining,
    puzzleAssignments,
    setPuzzleAssignments,
    puzzleComplete,
    puzzleError,
    voice,
    reload,
    start,
    submit,
    checkPuzzle,
  };
}
