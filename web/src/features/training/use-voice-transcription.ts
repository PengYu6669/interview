"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { PcmRecorder } from "@/features/interview-room/pcm-recorder";

type VoiceStatus = "idle" | "connecting" | "listening" | "recognizing";

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

export function useVoiceTranscription(
  sessionId: string,
  onTranscript: (text: string) => void,
) {
  const recorderRef = useRef<PcmRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const clearTimers = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    timerRef.current = null;
    timeoutRef.current = null;
  }, []);

  const cleanup = useCallback(async () => {
    clearTimers();
    await recorderRef.current?.stop();
    recorderRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
  }, [clearTimers]);

  useEffect(() => () => { void cleanup(); }, [cleanup]);

  const stop = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    clearTimers();
    setStatus("recognizing");
    recorderRef.current = null;
    await recorder.stop();
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(new ArrayBuffer(0));
    }
  }, [clearTimers]);

  async function start() {
    setError(""); setSeconds(0); setStatus("connecting");
    try {
      const ticketResponse = await fetch(`/api/coaching-sessions/${sessionId}/speech-ticket`, { method: "POST" });
      const ticketPayload: unknown = await ticketResponse.json();
      if (!ticketResponse.ok) throw new Error(errorMessage(ticketPayload, "语音服务启动失败"));
      const ticket = (ticketPayload as { ticket?: string }).ticket;
      if (!ticket) throw new Error("语音服务返回了无效票据");
      const configuredBase = process.env.NEXT_PUBLIC_INTERVIEW_WS_URL;
      const socketBase = (configuredBase || `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8000`).replace(/\/$/, "");
      const socket = new WebSocket(`${socketBase}/v1/coaching-sessions/${sessionId}/speech?ticket=${encodeURIComponent(ticket)}`);
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;
      socket.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as { type?: string; text?: string; detail?: string };
        if (message.type === "transcript") onTranscriptRef.current(message.text ?? "");
        if (message.type === "completed") { clearTimers(); setStatus("idle"); socket.close(); socketRef.current = null; }
        if (message.type === "error") { void cleanup(); setStatus("idle"); setError(message.detail ?? "语音识别失败"); }
      };
      socket.onerror = () => { void cleanup(); setStatus("idle"); setError("语音连接中断，请检查网络后重试"); };
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => { socket.close(); reject(new Error("语音服务连接超时")); }, 10_000);
        socket.addEventListener("open", () => { window.clearTimeout(timeout); resolve(); }, { once: true });
        socket.addEventListener("error", () => { window.clearTimeout(timeout); reject(new Error("无法连接语音服务")); }, { once: true });
      });
      const recorder = new PcmRecorder();
      recorderRef.current = recorder;
      await recorder.start((frame) => { if (socket.readyState === WebSocket.OPEN) socket.send(frame); });
      setStatus("listening");
      timerRef.current = window.setInterval(() => setSeconds((value) => value + 1), 1_000);
      timeoutRef.current = window.setTimeout(() => void stop(), 58_000);
    } catch (cause) {
      await cleanup(); setStatus("idle"); setError(cause instanceof Error ? cause.message : "语音服务启动失败");
    }
  }

  return { status, seconds, error, start, stop };
}
