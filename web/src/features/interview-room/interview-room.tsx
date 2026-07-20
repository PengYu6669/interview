"use client";

import { AlertTriangle, ArrowLeft, AudioLines, Camera, Captions, CheckCircle2, Clock3, Code2, LoaderCircle, Mic, MicOff, PanelRightOpen, Pause, PhoneOff, Play, RefreshCw, Send, Settings, Square, Video, VideoOff, Volume2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { InterviewRuntimeData, InterviewSessionData, interviewRuntimeSchema, interviewSessionSchema } from "@/lib/interview-session";
import { trainingContextLabels } from "@/lib/training-context";
import { clearAnswerDraft, draftMatchesRuntime, readAnswerDraft, writeAnswerDraft } from "./answer-draft";
import { ConnectionBanner, InterviewConnectionState } from "./connection-banner";
import { CodingBoardDrawer } from "./coding-board-drawer";
import { PcmRecorder } from "./pcm-recorder";
import { VoiceActivityDetector } from "./voice-activity";
import { SystemDesignBoard } from "./system-design-board";

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload && typeof payload.detail === "string" ? payload.detail : fallback;
}

export function InterviewRoom({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<InterviewSessionData | null>(null);
  const [runtime, setRuntime] = useState<InterviewRuntimeData | null>(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(sessionId ? "" : "缺少面试会话，请从面试蓝图重新进入。");
  const [cameraOn, setCameraOn] = useState(false);
  const [muted, setMuted] = useState(true);
  const [microphoneReady, setMicrophoneReady] = useState(false);
  const [deviceMessage, setDeviceMessage] = useState("尚未检测摄像头和麦克风");
  const [textPanel, setTextPanel] = useState(false);
  const [answer, setAnswer] = useState("");
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [answerError, setAnswerError] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [answerMode, setAnswerMode] = useState<"text" | "voice">("text");
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [sessionAction, setSessionAction] = useState<"pause" | "resume" | "end" | "">("");
  const [endConfirmation, setEndConfirmation] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [captionsOn, setCaptionsOn] = useState(true);
  const [autoVoice, setAutoVoice] = useState(true);
  const [voiceStatus, setVoiceStatus] = useState<"idle" | "listening" | "recognizing" | "thinking" | "speaking">("idle");
  const [connectionState, setConnectionState] = useState<InterviewConnectionState>("online");
  const [draftRestored, setDraftRestored] = useState(false);
  const [submissionUncertain, setSubmissionUncertain] = useState(false);
  const [dismissedCodingScope, setDismissedCodingScope] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const speakingRef = useRef(false);
  const speechFinishRef = useRef<(() => void) | null>(null);
  const recorderRef = useRef<PcmRecorder | null>(null);
  const voiceActivityRef = useRef(new VoiceActivityDetector());
  const speechSocketRef = useRef<WebSocket | null>(null);
  const recordingTimerRef = useRef<number | null>(null);
  const recordingStopTimeoutRef = useRef<number | null>(null);
  const recordingRef = useRef(false);
  const autoEndRequestedRef = useRef(false);
  const transcriptRef = useRef("");
  const submittingRef = useRef(false);
  const clientMessageIdRef = useRef<string | null>(null);
  const continuousVoiceRef = useRef(true);
  const recordingElapsedRef = useRef(0);
  const recordingStartedAtRef = useRef<number | null>(null);
  const interruptionCheckedRef = useRef(false);
  const interruptionPendingRef = useRef(false);
  const interruptedRef = useRef(false);
  const interruptionPromiseRef = useRef<Promise<void> | null>(null);
  const runtimeRef = useRef<InterviewRuntimeData | null>(null);
  const answerRef = useRef("");
  const networkAvailableRef = useRef(true);
  const expectedSpeechCloseRef = useRef(false);
  const connectionRestoredTimerRef = useRef<number | null>(null);
  const cancelVoiceCaptureRef = useRef<() => Promise<void>>(async () => undefined);
  const recoverConnectionRef = useRef<() => Promise<void>>(async () => undefined);
  const changeSessionStateRef = useRef<(action: "pause" | "resume" | "end") => Promise<void>>(async () => undefined);
  cancelVoiceCaptureRef.current = cancelVoiceCapture;
  recoverConnectionRef.current = recoverConnection;
  changeSessionStateRef.current = changeSessionState;

  useEffect(() => {
    let active = true;
    if (!sessionId) return;
    void fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}`, { cache: "no-store" }).then(async (response) => {
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "面试会话读取失败"));
      const parsed = interviewSessionSchema.parse(payload);
      if (active) setSession(parsed);
      if (parsed.status !== "planned") {
        const runtimeResponse = await fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/runtime`, { cache: "no-store" });
        const runtimePayload: unknown = await runtimeResponse.json();
        if (!runtimeResponse.ok) throw new Error(errorMessage(runtimePayload, "面试进度读取失败"));
        if (active) applyRuntime(interviewRuntimeSchema.parse(runtimePayload));
      }
      if (active) setConnectionState("online");
    }).catch((caught) => {
      if (active) {
        setConnectionState(navigator.onLine ? "unavailable" : "offline");
        setError(caught instanceof Error ? caught.message : "面试会话读取失败");
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const speechFinish = speechFinishRef.current;
      speechFinishRef.current = null;
      audioRef.current?.pause();
      audioRef.current = null;
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
      speakingRef.current = false;
      speechFinish?.();
      expectedSpeechCloseRef.current = true;
      speechSocketRef.current?.close();
      void recorderRef.current?.stop();
      recordingRef.current = false;
      if (recordingTimerRef.current) window.clearInterval(recordingTimerRef.current);
      if (recordingStopTimeoutRef.current) window.clearTimeout(recordingStopTimeoutRef.current);
      if (connectionRestoredTimerRef.current) window.clearTimeout(connectionRestoredTimerRef.current);
    };
  }, [sessionId]);

  useEffect(() => {
    answerRef.current = answer;
  }, [answer]);

  useEffect(() => {
    if (!runtime || runtime.status !== "started" || !answer.trim()) return;
    persistCurrentDraft(runtime, answer, answerMode);
  }, [answer, answerMode, runtime]);

  useEffect(() => {
    networkAvailableRef.current = navigator.onLine;
    const handleOffline = () => {
      networkAvailableRef.current = false;
      continuousVoiceRef.current = false;
      setConnectionState("offline");
      stopSpeechPlayback();
      if (answerRef.current.trim()) {
        setTextPanel(true);
        setDraftRestored(true);
      }
      void cancelVoiceCaptureRef.current();
    };
    const handleOnline = () => {
      networkAvailableRef.current = true;
      void recoverConnectionRef.current();
    };
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    if (!navigator.onLine) handleOffline();
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, [sessionId]);

  useEffect(() => {
    if (videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current;
  }, [cameraOn, runtime]);

  useEffect(() => {
    if (runtime?.status !== "started") return;
    const timer = window.setInterval(() => {
      setRemainingSeconds((seconds) => Math.max(0, seconds - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [runtime?.status]);

  useEffect(() => {
    if (runtime?.status !== "started" || remainingSeconds !== 0 || autoEndRequestedRef.current || submittingAnswer) return;
    autoEndRequestedRef.current = true;
    void changeSessionStateRef.current("end");
  }, [remainingSeconds, runtime, submittingAnswer]);

  function applyRuntime(nextRuntime: InterviewRuntimeData) {
    runtimeRef.current = nextRuntime;
    setRuntime(nextRuntime);
    setRemainingSeconds(nextRuntime.remaining_seconds);
    if (nextRuntime.remaining_seconds > 0) autoEndRequestedRef.current = false;
    const savedDraft = readAnswerDraft(nextRuntime.id);
    if (!savedDraft) return;
    if (!draftMatchesRuntime(savedDraft, nextRuntime) || nextRuntime.status === "completed" || nextRuntime.status === "ended") {
      clearAnswerDraft(nextRuntime.id);
      return;
    }
    if (!answerRef.current.trim()) {
      answerRef.current = savedDraft.answer;
      setAnswer(savedDraft.answer);
      setAnswerMode(savedDraft.answer_mode);
      clientMessageIdRef.current = savedDraft.client_message_id;
      setSubmissionUncertain(Boolean(savedDraft.client_message_id));
      setTextPanel(true);
      setDraftRestored(true);
    }
  }

  function persistCurrentDraft(
    targetRuntime: InterviewRuntimeData,
    answerText: string,
    mode: "text" | "voice",
  ) {
    if (!answerText.trim() || !targetRuntime.current_question) return;
    writeAnswerDraft({
      session_id: targetRuntime.id,
      question_number: targetRuntime.current_question_number,
      question_kind: targetRuntime.current_question_kind === "follow_up" ? "follow_up" : "main",
      question: targetRuntime.current_question,
      answer: answerText.trim(),
      answer_mode: mode,
      client_message_id: clientMessageIdRef.current,
      updated_at: new Date().toISOString(),
    });
  }

  async function recoverConnection() {
    if (!networkAvailableRef.current) {
      setConnectionState("offline");
      return;
    }
    const currentRuntime = runtimeRef.current;
    if (!currentRuntime) {
      window.location.reload();
      return;
    }
    setConnectionState("recovering");
    try {
      const response = await fetch(`/api/interview-sessions/${currentRuntime.id}/runtime`, {
        cache: "no-store",
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "面试连接恢复失败"));
      applyRuntime(interviewRuntimeSchema.parse(payload));
      continuousVoiceRef.current = false;
      setConnectionState("restored");
      if (connectionRestoredTimerRef.current) window.clearTimeout(connectionRestoredTimerRef.current);
      connectionRestoredTimerRef.current = window.setTimeout(() => {
        setConnectionState("online");
      }, 4_000);
    } catch (caught) {
      setConnectionState(navigator.onLine ? "unavailable" : "offline");
      setAnswerError(caught instanceof Error ? caught.message : "面试连接恢复失败");
    }
  }

  async function checkDevices() {
    setDeviceMessage("正在请求设备权限…");
    streamRef.current?.getTracks().forEach((track) => track.stop());
    const tracks: MediaStreamTrack[] = [];
    let audioAvailable = false;
    let videoAvailable = false;
    try {
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
      tracks.push(...audioStream.getAudioTracks());
      audioAvailable = true;
    } catch {
      audioAvailable = false;
    }
    try {
      const videoStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      tracks.push(...videoStream.getVideoTracks());
      videoAvailable = true;
    } catch {
      videoAvailable = false;
    }
    const stream = new MediaStream(tracks);
    streamRef.current = stream;
    if (videoRef.current) videoRef.current.srcObject = stream;
    setMicrophoneReady(audioAvailable);
    setMuted(!audioAvailable);
    setCameraOn(videoAvailable);
    setDeviceMessage(audioAvailable && videoAvailable ? "摄像头和麦克风工作正常" : audioAvailable ? "麦克风正常，摄像头不可用" : videoAvailable ? "摄像头正常，麦克风不可用，可使用文字回答" : "无法使用摄像头和麦克风，请检查浏览器权限");
  }

  function toggleCamera() {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) { void checkDevices(); return; }
    track.enabled = !track.enabled;
    setCameraOn(track.enabled);
  }

  function toggleMic() {
    const track = streamRef.current?.getAudioTracks()[0];
    if (!track) { void checkDevices(); return; }
    track.enabled = !track.enabled;
    setMuted(!track.enabled);
    setMicrophoneReady(true);
  }

  async function startInterview() {
    if (!session) return;
    setStarting(true);
    setError("");
    try {
      const response = await fetch(`/api/interview-sessions/${session.id}/start`, { method: "POST" });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "面试开始失败"));
      const startedRuntime = interviewRuntimeSchema.parse(payload);
      applyRuntime(startedRuntime);
      setConnectionState("online");
      await playQuestion(spokenQuestion(startedRuntime, true));
      if (continuousVoiceRef.current && !isCodingPhase(startedRuntime)) await startVoiceAnswer(startedRuntime);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "面试开始失败");
      setConnectionState(navigator.onLine ? "unavailable" : "offline");
    } finally {
      setStarting(false);
    }
  }

  async function submitAnswer(answerText = answer, mode = answerMode, targetRuntime = runtime) {
    const normalizedAnswer = answerText.trim();
    if (!targetRuntime || !normalizedAnswer || submittingRef.current) return;
    submittingRef.current = true;
    setSubmittingAnswer(true);
    if (mode === "voice") setVoiceStatus("thinking");
    setAnswerError("");
    clientMessageIdRef.current ??= crypto.randomUUID();
    persistCurrentDraft(targetRuntime, normalizedAnswer, mode);
    try {
      const response = await fetch(`/api/interview-sessions/${targetRuntime.id}/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_message_id: clientMessageIdRef.current, answer: normalizedAnswer, answer_mode: mode }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "回答提交失败"));
      const nextRuntime = interviewRuntimeSchema.parse(payload);
      clearAnswerDraft(targetRuntime.id);
      setDraftRestored(false);
      setSubmissionUncertain(false);
      answerRef.current = "";
      clientMessageIdRef.current = null;
      setAnswer("");
      transcriptRef.current = "";
      setTextPanel(false);
      applyRuntime(nextRuntime);
      if (mode === "voice" && nextRuntime.status === "completed") {
        await playQuestion(spokenQuestion(nextRuntime));
      }
      if (mode === "voice" && nextRuntime.status === "started" && nextRuntime.current_question) {
        await playQuestion(spokenQuestion(nextRuntime));
        if (continuousVoiceRef.current && !isCodingPhase(nextRuntime)) await startVoiceAnswer(nextRuntime, true);
      } else {
        setVoiceStatus("idle");
      }
      setConnectionState("online");
    } catch (caught) {
      setSubmissionUncertain(Boolean(clientMessageIdRef.current));
      setAnswerError(caught instanceof Error ? caught.message : "回答提交失败");
      setVoiceStatus("idle");
      setConnectionState(navigator.onLine ? "unavailable" : "offline");
    } finally {
      submittingRef.current = false;
      setSubmittingAnswer(false);
    }
  }

  function stopSpeechPlayback() {
    const finish = speechFinishRef.current;
    speechFinishRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    speakingRef.current = false;
    setSpeaking(false);
    setVoiceStatus("idle");
    finish?.();
  }

  async function playQuestion(question = runtime?.current_question ?? "") {
    if (!question || speakingRef.current) return;
    speakingRef.current = true;
    setSpeaking(true);
    setVoiceStatus("speaking");
    setSpeechError("");
    try {
      const response = await fetch("/api/tts/xfyun", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: question }) });
      if (!response.ok) throw new Error(errorMessage(await response.json(), "面试官语音播放失败"));
      const url = URL.createObjectURL(await response.blob());
      audioUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      await new Promise<void>((resolve) => {
        speechFinishRef.current = resolve;
        audio.addEventListener("ended", stopSpeechPlayback, { once: true });
        audio.addEventListener("error", () => {
          setSpeechError("音频播放失败，已切换为字幕提问");
          stopSpeechPlayback();
        }, { once: true });
        void audio.play().catch(() => {
          setSpeechError("浏览器阻止了自动播放，请使用重播按钮");
          stopSpeechPlayback();
        });
      });
    } catch (caught) {
      setSpeechError(caught instanceof Error ? caught.message : "面试官语音播放失败");
      stopSpeechPlayback();
    }
  }

  async function startVoiceAnswer(targetRuntime = runtime, allowDuringSubmission = false) {
    if (!targetRuntime || recordingRef.current || transcribing || (submittingRef.current && !allowDuringSubmission)) return;
    if (!networkAvailableRef.current) {
      setConnectionState("offline");
      setAnswerError("网络已断开，恢复连接后才能开始语音回答");
      return;
    }
    setAnswerError("");
    clearAnswerDraft(targetRuntime.id);
    setDraftRestored(false);
    setSubmissionUncertain(false);
    clientMessageIdRef.current = null;
    answerRef.current = "";
    setAnswer("");
    transcriptRef.current = "";
    recordingElapsedRef.current = 0;
    interruptionCheckedRef.current = false;
    interruptionPendingRef.current = false;
    interruptedRef.current = false;
    voiceActivityRef.current.reset();
    setAnswerMode("voice");
    setTextPanel(false);
    setVoiceStatus("listening");
    try {
      const ticketResponse = await fetch(`/api/interview-sessions/${targetRuntime.id}/speech-ticket`, { method: "POST" });
      const ticketPayload: unknown = await ticketResponse.json();
      if (!ticketResponse.ok) throw new Error(errorMessage(ticketPayload, "语音服务启动失败"));
      const ticket = (ticketPayload as { ticket?: string }).ticket;
      if (!ticket) throw new Error("语音服务返回了无效票据");
      const configuredBase = process.env.NEXT_PUBLIC_INTERVIEW_WS_URL;
      const socketBase = (configuredBase || `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8000`).replace(/\/$/, "");
      const socket = new WebSocket(`${socketBase}/v1/interview-sessions/${targetRuntime.id}/speech?ticket=${encodeURIComponent(ticket)}`);
      socket.binaryType = "arraybuffer";
      speechSocketRef.current = socket;
      expectedSpeechCloseRef.current = false;
      socket.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as { type?: string; text?: string; detail?: string };
        if (message.type === "transcript") {
          transcriptRef.current = message.text ?? "";
          setAnswer(transcriptRef.current);
          if (
            targetRuntime.pressure_level >= 4
            && targetRuntime.phases[targetRuntime.current_phase_index]?.kind !== "candidate_qa"
            && recordingElapsedRef.current >= 18
            && transcriptRef.current.trim().length >= 60
            && !interruptionCheckedRef.current
          ) {
            interruptionCheckedRef.current = true;
            interruptionPromiseRef.current = assessInterruption(targetRuntime);
          }
        }
        if (message.type === "completed") {
          setTranscribing(false);
          expectedSpeechCloseRef.current = true;
          socket.close();
          void finalizeRecognizedAnswer(targetRuntime);
        }
        if (message.type === "error") { expectedSpeechCloseRef.current = true; setVoiceStatus("idle"); setTranscribing(false); recordingRef.current = false; setRecording(false); setAnswerError(message.detail ?? "语音识别失败"); }
      };
      await new Promise<void>((resolve, reject) => {
        let opened = false;
        const timeout = window.setTimeout(() => {
          socket.close();
          reject(new Error("语音服务连接超时"));
        }, 10_000);
        socket.addEventListener("open", () => {
          opened = true;
          window.clearTimeout(timeout);
          resolve();
        }, { once: true });
        socket.addEventListener("error", () => {
          if (!opened) {
            window.clearTimeout(timeout);
            reject(new Error("无法连接语音服务，请检查服务是否启动"));
          }
        }, { once: true });
        socket.addEventListener("close", () => {
          if (!opened) {
            window.clearTimeout(timeout);
            reject(new Error("语音服务拒绝连接，请重新进入面试后再试"));
          }
        }, { once: true });
      });
      socket.onerror = () => { setVoiceStatus("idle"); setAnswerError("语音连接中断，请检查网络后重试"); };
      socket.onclose = () => {
        const unexpected = !expectedSpeechCloseRef.current;
        recordingRef.current = false;
        setRecording(false);
        setTranscribing(false);
        if (speechSocketRef.current === socket) speechSocketRef.current = null;
        void recorderRef.current?.stop();
        if (unexpected && runtimeRef.current?.status === "started") {
          if (transcriptRef.current.trim()) {
            answerRef.current = transcriptRef.current;
            setAnswer(transcriptRef.current);
            setTextPanel(true);
            setDraftRestored(true);
            persistCurrentDraft(targetRuntime, transcriptRef.current, "voice");
          }
          setConnectionState(navigator.onLine ? "unavailable" : "offline");
          setAnswerError("语音连接意外中断，本轮已识别内容已保留");
        }
      };
      const recorder = new PcmRecorder();
      recorderRef.current = recorder;
      await recorder.start(
        (frame) => {
          if (socket.readyState === WebSocket.OPEN) socket.send(frame);
          if (recordingRef.current && voiceActivityRef.current.push(frame)) void stopVoiceAnswer();
        },
        streamRef.current,
      );
      recordingRef.current = true;
      setVoiceStatus("listening");
      setRecording(true);
      setRecordingSeconds(0);
      recordingStartedAtRef.current = Date.now();
      if (recordingTimerRef.current) window.clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = window.setInterval(() => {
        const startedAt = recordingStartedAtRef.current;
        if (startedAt === null) return;
        const elapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1_000));
        recordingElapsedRef.current = elapsed;
        setRecordingSeconds(elapsed);
      }, 1_000);
      recordingStopTimeoutRef.current = window.setTimeout(() => void stopVoiceAnswer(), 58_000);
    } catch (caught) {
      await recorderRef.current?.stop();
      expectedSpeechCloseRef.current = true;
      speechSocketRef.current?.close();
      recordingRef.current = false;
      setRecording(false);
      setTranscribing(false);
      setVoiceStatus("idle");
      setAnswerError(caught instanceof Error ? caught.message : "语音服务启动失败");
    }
  }

  async function cancelVoiceCapture() {
    if (recordingTimerRef.current) window.clearInterval(recordingTimerRef.current);
    if (recordingStopTimeoutRef.current) window.clearTimeout(recordingStopTimeoutRef.current);
    recordingTimerRef.current = null;
    recordingStopTimeoutRef.current = null;
    recordingRef.current = false;
    recordingStartedAtRef.current = null;
    expectedSpeechCloseRef.current = true;
    await recorderRef.current?.stop();
    speechSocketRef.current?.close();
    speechSocketRef.current = null;
    setRecording(false);
    setTranscribing(false);
    setVoiceStatus("idle");
    if (transcriptRef.current.trim()) {
      answerRef.current = transcriptRef.current;
      setAnswer(transcriptRef.current);
      const currentRuntime = runtimeRef.current;
      if (currentRuntime) persistCurrentDraft(currentRuntime, transcriptRef.current, "voice");
      setTextPanel(true);
      setDraftRestored(true);
    }
  }

  async function stopVoiceAnswer() {
    if (!recordingRef.current) return;
    recordingRef.current = false;
    if (recordingTimerRef.current) window.clearInterval(recordingTimerRef.current);
    if (recordingStopTimeoutRef.current) window.clearTimeout(recordingStopTimeoutRef.current);
    recordingTimerRef.current = null;
    recordingStopTimeoutRef.current = null;
    recordingStartedAtRef.current = null;
    setRecording(false);
    setTranscribing(true);
    setVoiceStatus("recognizing");
    await recorderRef.current?.stop();
    const socket = speechSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN) socket.send(new ArrayBuffer(0));
  }

  async function assessInterruption(targetRuntime: InterviewRuntimeData) {
    if (interruptionPendingRef.current || !transcriptRef.current.trim()) return;
    interruptionPendingRef.current = true;
    clientMessageIdRef.current ??= crypto.randomUUID();
    try {
      const response = await fetch(`/api/interview-sessions/${targetRuntime.id}/interruptions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_message_id: clientMessageIdRef.current,
          partial_answer: transcriptRef.current,
          elapsed_seconds: Math.min(55, Math.max(12, recordingElapsedRef.current)),
        }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "实时打断判断失败"));
      const result = payload as { interrupted?: boolean; runtime?: unknown };
      if (!result.interrupted) return;
      const nextRuntime = interviewRuntimeSchema.parse(result.runtime);
      interruptedRef.current = true;
      recordingRef.current = false;
      if (recordingTimerRef.current) window.clearInterval(recordingTimerRef.current);
      if (recordingStopTimeoutRef.current) window.clearTimeout(recordingStopTimeoutRef.current);
      recordingTimerRef.current = null;
      recordingStopTimeoutRef.current = null;
      await recorderRef.current?.stop();
      expectedSpeechCloseRef.current = true;
      speechSocketRef.current?.close();
      setRecording(false);
      setTranscribing(false);
      applyRuntime(nextRuntime);
      setAnswer("");
      transcriptRef.current = "";
      clientMessageIdRef.current = null;
      await playQuestion(spokenQuestion(nextRuntime));
      if (continuousVoiceRef.current) await startVoiceAnswer(nextRuntime);
    } catch (caught) {
      console.warn("实时打断判断已跳过", caught instanceof Error ? caught.message : "未知错误");
    } finally {
      interruptionPendingRef.current = false;
    }
  }

  async function finalizeRecognizedAnswer(targetRuntime: InterviewRuntimeData) {
    await interruptionPromiseRef.current;
    interruptionPromiseRef.current = null;
    if (interruptedRef.current) return;
    if (transcriptRef.current.trim()) {
      await submitAnswer(transcriptRef.current, "voice", targetRuntime);
    } else {
      setVoiceStatus("idle");
      setAnswerError("没有识别到有效回答，请靠近麦克风后重试");
    }
  }

  async function changeSessionState(action: "pause" | "resume" | "end") {
    if (!runtime || sessionAction) return;
    if (submittingRef.current) {
      if (action === "end") autoEndRequestedRef.current = false;
      setAnswerError("面试官正在处理本轮回答，请等待保存完成后再切换状态");
      return;
    }
    setSessionAction(action);
    setAnswerError("");
    try {
      continuousVoiceRef.current = action === "resume" ? autoVoice : false;
      stopSpeechPlayback();
      if (recordingRef.current || transcribing) await cancelVoiceCapture();
      if (interruptionPromiseRef.current) {
        await interruptionPromiseRef.current;
        interruptionPromiseRef.current = null;
      }
      const endpoint = action === "resume" ? "start" : action;
      const response = await fetch(`/api/interview-sessions/${runtime.id}/${endpoint}`, { method: "POST" });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "面试状态更新失败"));
      const nextRuntime = interviewRuntimeSchema.parse(payload);
      if (action === "end") {
        clearAnswerDraft(runtime.id);
        setDraftRestored(false);
        setSubmissionUncertain(false);
        answerRef.current = "";
        setAnswer("");
      }
      applyRuntime(nextRuntime);
      if (action === "resume") {
        continuousVoiceRef.current = autoVoice;
        if (!answerRef.current.trim() && nextRuntime.current_question) {
          await playQuestion(spokenQuestion(nextRuntime));
          if (continuousVoiceRef.current) await startVoiceAnswer(nextRuntime);
        }
      }
      setConnectionState("online");
      setEndConfirmation(false);
    } catch (caught) {
      setAnswerError(caught instanceof Error ? caught.message : "面试状态更新失败");
      if (action === "end") autoEndRequestedRef.current = false;
    } finally {
      setSessionAction("");
    }
  }

  if (loading) return <div className="interview-entry-state"><LoaderCircle className="spin" size={26} /><strong>正在进入面试空间</strong></div>;
  if (error && !session) return <div className="interview-entry-state error"><AlertTriangle size={26} /><strong>无法进入面试</strong><p>{error}</p><div className="interview-entry-actions"><button type="button" className="primary-cta" onClick={() => window.location.reload()}><RefreshCw size={15} />重新连接</button><Link href="/history" className="secondary-button">返回训练记录</Link></div></div>;
  if (!session) return null;

  const sessionContext = trainingContextLabels(session);

  if (!runtime) return <div className="waiting-room">
    <header className="waiting-header"><Link href="/blueprint"><ArrowLeft size={16} />返回面试蓝图</Link><div><span className="meeting-logo">面</span><strong>模拟面试等候室</strong></div><span>设备检查</span></header>
    <main className="waiting-layout"><section className="waiting-preview"><div className="waiting-video-frame">{cameraOn ? <video ref={videoRef} autoPlay muted playsInline /> : <div className="waiting-avatar"><span>你</span><p>摄像头已关闭</p></div>}<div className="waiting-preview-name">{microphoneReady && !muted ? <Mic size={14} /> : <MicOff size={14} />}你</div></div><div className="waiting-device-controls"><button type="button" className={muted ? "off" : ""} onClick={toggleMic} aria-label={muted ? "打开麦克风" : "关闭麦克风"}>{muted ? <MicOff /> : <Mic />}</button><button type="button" className={!cameraOn ? "off" : ""} onClick={toggleCamera} aria-label={cameraOn ? "关闭摄像头" : "打开摄像头"}>{cameraOn ? <Video /> : <VideoOff />}</button></div></section><aside className="waiting-summary"><span className="waiting-kicker">即将开始 · {sessionContext.type}</span><h1>{session.target_role} · {sessionContext.round}</h1><p>{session.summary}</p><dl>{session.target_company && <div><dt>目标公司</dt><dd>{session.target_company}</dd></div>}<div><dt>目标职级</dt><dd>{sessionContext.level}</dd></div><div><dt>面试时长</dt><dd>{session.duration_minutes} 分钟</dd></div><div><dt>考察阶段</dt><dd>{session.phases.length} 个</dd></div><div><dt>回答方式</dt><dd>语音 / 文字</dd></div></dl><button className="device-check-button" type="button" onClick={() => void checkDevices()}><Camera size={16} />检测摄像头和麦克风</button><div className={`device-status ${microphoneReady ? "ready" : ""}`}>{microphoneReady ? <CheckCircle2 size={15} /> : <Volume2 size={15} />}<span>{deviceMessage}</span></div>{error && <p className="waiting-error">{error}</p>}<button className="join-interview-button" type="button" disabled={starting} onClick={() => void startInterview()}>{starting ? <LoaderCircle className="spin" size={17} /> : null}{starting ? "正在进入" : "进入面试"}</button></aside></main>
  </div>;

  if (runtime.status === "completed" || runtime.status === "ended") return <div className="interview-entry-state complete"><CheckCircle2 size={30} /><strong>{runtime.status === "completed" ? "本场面试已完成并保存" : "本场面试已结束并保存"}</strong><p>{runtime.status === "completed" ? `本场 ${runtime.answered_questions} 道主问题和全部追问回答已写入训练记录。` : `面试进度停在第 ${Math.min(runtime.answered_questions + 1, runtime.total_questions)} 题，已提交的回答均已写入训练记录。`}</p><span className="interview-save-note">复盘报告尚未生成，点击下方按钮后才会调用 AI。</span>{runtime.status === "completed" && (runtime.interviewer_reply || runtime.closing_statement) && <blockquote className="interview-closing-statement">{[runtime.interviewer_reply, runtime.closing_statement].filter(Boolean).join(" ")}</blockquote>}<div className="interview-complete-actions"><Link href={`/report?session=${runtime.id}`} className="primary-cta">生成复盘报告</Link><Link href="/history" className="secondary-button">查看已保存记录</Link></div></div>;

  const currentPhase = runtime.phases[runtime.current_phase_index];
  const codingScope = currentPhase?.kind === "coding" ? `${runtime.id}:${runtime.current_phase_index}:${runtime.current_question_index}` : null;
  const codingPanel = Boolean(codingScope && dismissedCodingScope !== codingScope && !textPanel);
  const connectionReady = connectionState === "online" || connectionState === "restored";
  const phaseProgress = `${currentPhase?.name ?? "当前环节"}${runtime.current_question_kind === "follow_up" ? ` · 追问 ${runtime.follow_up_count}` : ` · 第 ${runtime.current_question_number} 题`}`;
  return <div className="meeting-app feishu-room">
    <header className="meeting-header"><div className="meeting-title"><span className="meeting-logo">面</span><div><h1>{runtime.target_company ? `${runtime.target_company} · ` : ""}{runtime.target_role}</h1><p>{phaseProgress}</p></div></div><div className="meeting-meta"><span className="meeting-timer"><Clock3 size={15} />{formatDuration(remainingSeconds)}</span><span className="recording-mark"><i />REC</span><button className="mobile-progress-button" type="button" title="查看面试进度" aria-label="查看面试进度" aria-expanded={progressOpen} onClick={() => setProgressOpen((value) => !value)}><PanelRightOpen size={18} /></button><button type="button" title="面试设置" aria-label="面试设置" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((value) => !value)}><Settings size={18} /></button><button type="button" title="退出面试" aria-label="退出面试" onClick={() => setEndConfirmation(true)}><X size={18} /></button></div></header>
    <ConnectionBanner state={connectionState} hasDraft={Boolean(answer.trim())} onRetry={() => void recoverConnection()} />
    <main className={`meeting-main ${textPanel ? "with-answer-panel" : codingPanel && currentPhase?.kind === "coding" ? "with-coding-panel" : ""}`}>
      <section className="video-stage">
        <div className="interviewer-tile"><div className="participant-label">INTERVIEWER</div><div className="interviewer-presence"><div className="interviewer-avatar">林</div><strong>林老师</strong><span>AI 技术面试官</span><div className={`sound-wave ${speaking ? "is-speaking" : ""}`} aria-label={speaking ? "面试官正在说话" : "面试官当前静音"}>{Array.from({ length: 30 }, (_, index) => <i key={index} style={{ "--wave-index": index } as React.CSSProperties} />)}</div></div></div>
        {voiceStatus !== "idle" && <div className={`interview-voice-status ${voiceStatus}`} aria-live="polite">{voiceStatus === "listening" ? <><span className="recording-pulse" />正在听你回答 · {recordingSeconds} 秒</> : voiceStatus === "recognizing" ? <><LoaderCircle className="spin" size={16} />正在整理你的回答</> : voiceStatus === "thinking" ? <><LoaderCircle className="spin" size={16} />面试官正在思考追问</> : <><Volume2 size={16} />面试官正在提问</>}</div>}
        {captionsOn && <QuestionCaption runtime={runtime} phaseName={currentPhase?.name ?? "当前阶段"} speaking={speaking} speechError={speechError} answerError={textPanel ? "" : answerError} canRetry={Boolean(answer.trim() && answerMode === "voice" && connectionReady)} submitting={submittingAnswer} onReplay={() => void playQuestion(spokenQuestion(runtime))} onRetry={() => void submitAnswer(answer, "voice", runtime)} />}
        <div className="answering-cue"><span>轮到你回答了，先结论，再展开</span><i /><i /><i /></div>
        <div className={`self-video ${cameraOn ? "camera-active" : ""}`}>{cameraOn ? <video ref={videoRef} autoPlay muted playsInline /> : <><VideoOff size={20} /><span>摄像头已关闭</span></>}<small>{muted ? <MicOff size={11} /> : <Mic size={11} />}{muted ? "麦克风静音" : "正在收音"}</small></div>
        <section className="ai-trace" aria-label="AI 工作状态"><header><span className="speaking-dot" /><strong>AI 面试官 · 正在形成追问策略</strong><b>LIVE</b></header><div className="ai-trace-steps"><article className="done"><CheckCircle2 size={15} /><div><strong>读取简历与 JD</strong><span>已定位本轮岗位与经历上下文</span></div></article><article className="active"><span className="speaking-dot" /><div><strong>理解当前回答</strong><span>正在结合项目细节判断追问方向</span></div></article><article><Clock3 size={15} /><div><strong>更新追问计划</strong><span>等待本轮回答完成后生成</span></div></article></div></section>
      </section>
      {currentPhase?.kind === "system_design" && <SystemDesignBoard sessionId={runtime.id} readOnly={runtime.status === "completed" || runtime.status === "ended"} />}
      {codingPanel && currentPhase?.kind === "coding" && <CodingBoardDrawer key={codingScope} sessionId={runtime.id} onClose={() => setDismissedCodingScope(codingScope)} />}
      {textPanel && <aside className="room-answer-panel"><div className="drawer-heading"><div><strong>{answerMode === "voice" ? "语音回答" : "文字回答"}</strong><span>{recording ? `正在听写 · ${recordingSeconds} 秒` : transcribing ? "正在等待最终识别结果" : submissionUncertain ? "上次提交结果未知，请先确认提交状态" : draftRestored ? "已恢复本轮草稿，确认内容后再提交" : answerMode === "voice" ? "可修正识别文字，确认后再提交" : "按真实面试方式组织你的回答"}</span></div><button type="button" disabled={transcribing} onClick={() => { if (recording) void stopVoiceAnswer(); else setTextPanel(false); }} aria-label="关闭回答"><X size={18} /></button></div><div className="answer-current-question"><span>{currentPhase?.name}</span><p>{runtime.current_question}</p></div>{draftRestored && <div className={`answer-recovered-note ${submissionUncertain ? "uncertain" : ""}`}><CheckCircle2 size={14} />{submissionUncertain ? "回答内容已锁定，将使用原消息编号确认，避免重复保存" : runtime.status === "paused" ? "本轮草稿已保留，继续面试后可以提交" : "本轮未提交内容已从当前标签页恢复"}</div>}{(recording || transcribing) && <div className="voice-live-state"><span className={recording ? "recording-pulse" : ""} />{recording ? "请自然回答，持续停顿约 3 秒后自动结束" : "正在完成动态修正…"}</div>}<textarea value={answer} onChange={(event) => { setAnswer(event.target.value); setDraftRestored(false); }} maxLength={20_000} placeholder={recording ? "识别文字会实时出现在这里…" : "按真实面试方式组织你的回答…"} readOnly={recording || transcribing || submissionUncertain} autoFocus />{answerError && <p className="room-answer-error" role="alert">{answerError}</p>}<div className="drawer-footer"><span>{answer.length.toLocaleString()} / 20,000</span>{recording ? <button className="stop-recording" type="button" onClick={() => void stopVoiceAnswer()}><Square size={14} />结束回答</button> : <button type="button" disabled={!answer.trim() || submittingAnswer || transcribing || !connectionReady || runtime.status === "paused"} onClick={() => void submitAnswer()}>{submittingAnswer ? <LoaderCircle className="spin" size={15} /> : <Send size={15} />}{submittingAnswer ? "面试官正在分析" : runtime.status === "paused" ? "继续面试后提交" : !connectionReady ? "等待连接恢复" : submissionUncertain ? "确认提交状态" : "确认并提交"}</button>}</div></aside>}
      <aside className={`meeting-sidebar ${progressOpen ? "progress-open" : ""}`}><div className="sidebar-title"><div><strong>面试进度</strong><span>{runtime.answered_questions} / {runtime.total_questions} 已完成</span></div><button className="mobile-progress-close" type="button" onClick={() => setProgressOpen(false)} aria-label="关闭面试进度"><X size={18} /></button></div><div className="phase-timeline">{runtime.phases.map((phase, index) => { const status = index < runtime.current_phase_index ? "done" : index === runtime.current_phase_index ? "active" : "pending"; return <div className={`timeline-phase ${status}`} key={phase.name}><span>{status === "done" ? <CheckCircle2 size={13} /> : index + 1}</span><div><strong>{phase.name}</strong><small>{status === "active" ? "正在进行" : status === "done" ? "已完成" : `预计 ${phase.minutes} 分钟`}</small><p>{phase.skills.slice(0, 3).join(" · ")}</p></div></div>; })}</div><section className="room-style-summary"><h2>本场风格</h2><StyleMeter label="压力" value={runtime.pressure_level} /><StyleMeter label="深度" value={runtime.depth_level} /><StyleMeter label="引导" value={runtime.guidance_level} /></section><div className="sidebar-notes"><AudioLines size={16} /><div><strong>连贯与稳定</strong><span>{connectionReady ? "节奏稳定，继续保持清晰、完整的表达。" : "连接恢复后将继续记录本轮回答。"}</span></div></div></aside></main>
    <footer className="meeting-controls"><div className="control-hint"><span className={`live-dot ${connectionReady ? "" : "disconnected"}`} />{!connectionReady ? "连接恢复前不会提交回答" : runtime.status === "paused" ? "计时与回答已暂停" : currentPhase?.kind === "coding" ? "完成代码后说明复杂度并提交回答" : voiceStatus === "thinking" ? "面试官正在分析你的回答" : recording ? "直接说话，持续停顿约 3 秒后自动提交" : transcribing ? "正在整理识别结果" : autoVoice ? "自动语音面试已就绪" : "手动语音模式"}</div><div className="control-group"><RoomControl active={!muted} label={muted ? "取消静音" : "静音"} onClick={toggleMic} icon={muted ? <MicOff /> : <Mic />} /><RoomControl active={cameraOn} label={cameraOn ? "关闭摄像头" : "开启摄像头"} onClick={toggleCamera} icon={cameraOn ? <Video /> : <VideoOff />} /><RoomControl active={runtime.status === "paused"} disabled={!connectionReady || submittingAnswer || transcribing} label={runtime.status === "paused" ? "继续面试" : "暂停面试"} onClick={() => void changeSessionState(runtime.status === "paused" ? "resume" : "pause")} icon={runtime.status === "paused" ? <Play /> : <Pause />} /><RoomControl active={recording} disabled={!connectionReady || submittingAnswer || speaking || submissionUncertain} label={recording ? "结束回答" : submittingAnswer || speaking ? "请稍候" : submissionUncertain ? "先确认提交" : "开始回答"} onClick={() => { if (runtime.status === "paused" || submittingAnswer || speaking || submissionUncertain) return; if (recording) void stopVoiceAnswer(); else { continuousVoiceRef.current = autoVoice; void startVoiceAnswer(runtime); } }} icon={recording ? <Square /> : submittingAnswer ? <LoaderCircle className="spin" /> : <AudioLines />} />{currentPhase?.kind === "coding" && <RoomControl active={codingPanel} label={codingPanel ? "收起代码板" : "打开代码板"} onClick={() => { setTextPanel(false); setDismissedCodingScope(codingPanel ? codingScope : null); }} icon={<Code2 />} />}<RoomControl active={textPanel && answerMode === "text"} label="文字回答" onClick={() => { if (runtime.status === "paused" || recording || transcribing || submittingAnswer || submissionUncertain) return; continuousVoiceRef.current = false; setAutoVoice(false); setAnswerMode("text"); if (!answerRef.current.trim()) clientMessageIdRef.current = null; if (codingScope) setDismissedCodingScope(codingScope); setTextPanel((value) => answerMode === "text" ? !value : true); }} icon={<Captions />} /><button className="hangup-button" type="button" title="结束面试" aria-label="结束面试" disabled={!connectionReady || submittingAnswer || transcribing} onClick={() => setEndConfirmation(true)}><PhoneOff size={20} /><span>结束并生成复盘</span></button></div><div className="control-mode"><span>压力 {runtime.pressure_level} · 深度 {runtime.depth_level} · 引导 {runtime.guidance_level}</span></div></footer>
    {settingsOpen && <div className="meeting-settings-popover" role="dialog" aria-label="面试设置"><div><strong>面试设置</strong><button type="button" onClick={() => setSettingsOpen(false)} aria-label="关闭设置"><X size={16} /></button></div><label><span><b>自动语音对话</b><small>面试官说完后自动开始聆听</small></span><input type="checkbox" checked={autoVoice} onChange={(event) => { setAutoVoice(event.target.checked); continuousVoiceRef.current = event.target.checked; }} /></label><label><span><b>问题字幕</b><small>在主画面显示当前问题和追问</small></span><input type="checkbox" checked={captionsOn} onChange={(event) => setCaptionsOn(event.target.checked)} /></label><dl><div><dt>压力</dt><dd>{runtime.pressure_level} / 5</dd></div><div><dt>深度</dt><dd>{runtime.depth_level} / 5</dd></div><div><dt>引导</dt><dd>{runtime.guidance_level} / 5</dd></div></dl></div>}
    {endConfirmation && <div className="modal-backdrop" role="presentation"><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="end-interview-title"><div className="dialog-icon"><PhoneOff size={20} /></div><h2 id="end-interview-title">确认结束这场面试？</h2><p>已提交的 {runtime.answered_questions} 道回答会被保存。当前问题不会自动提交，结束后不能继续本场面试。</p>{answerError && <p className="room-answer-error" role="alert">{answerError}</p>}<div><button className="secondary-action" type="button" disabled={sessionAction === "end"} onClick={() => setEndConfirmation(false)}>继续面试</button><button className="danger-action" type="button" disabled={sessionAction === "end"} onClick={() => void changeSessionState("end")}>{sessionAction === "end" ? <LoaderCircle className="spin" size={15} /> : <PhoneOff size={15} />}{sessionAction === "end" ? "正在结束" : "确认结束"}</button></div></section></div>}
  </div>;
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function spokenQuestion(runtime: InterviewRuntimeData, includeOpening = false) {
  const parts = [];
  if (includeOpening) parts.push(runtime.opening_statement, "好，那我们现在开始。第一个问题。 ");
  else if (runtime.interviewer_transition) parts.push(runtime.interviewer_transition);
  if (runtime.interviewer_reply) parts.push(runtime.interviewer_reply);
  if (runtime.current_question) parts.push(runtime.current_question);
  if (runtime.closing_statement) parts.push(runtime.closing_statement);
  return parts.join("。 ").replace(/。\s*。/g, "。");
}

function isCodingPhase(runtime: InterviewRuntimeData) {
  return runtime.phases[runtime.current_phase_index]?.kind === "coding";
}

function QuestionCaption({
  runtime,
  phaseName,
  speaking,
  speechError,
  answerError,
  canRetry,
  submitting,
  onReplay,
  onRetry,
}: {
  runtime: InterviewRuntimeData;
  phaseName: string;
  speaking: boolean;
  speechError: string;
  answerError: string;
  canRetry: boolean;
  submitting: boolean;
  onReplay: () => void;
  onRetry: () => void;
}) {
  return <div className="question-caption">
    <div><span>第 {runtime.current_question_number} 题</span>{runtime.current_question_kind === "follow_up" && <b>追问 {runtime.follow_up_count}</b>}<em>{phaseName}</em><button type="button" onClick={onReplay} disabled={speaking} title="重播面试官发言" aria-label="重播面试官发言">{speaking ? <LoaderCircle className="spin" size={15} /> : <Volume2 size={15} />}</button></div>
    {runtime.interviewer_transition && <small className="interviewer-transition">{runtime.interviewer_transition}</small>}
    {runtime.interviewer_reply && <div className="interviewer-reply"><strong>面试官回答</strong><p>{runtime.interviewer_reply}</p></div>}
    {runtime.current_question && <p>{runtime.current_question}</p>}
    {speechError && <small className="speech-error">{speechError}</small>}
    {answerError && <small className="speech-error" role="alert">{answerError}{canRetry && <button type="button" disabled={submitting} onClick={onRetry}>重试提交</button>}</small>}
  </div>;
}

function RoomControl({ icon, label, active, disabled = false, onClick }: { icon: React.ReactNode; label: string; active: boolean; disabled?: boolean; onClick: () => void }) {
  return <button className={`meeting-control ${active ? "control-active" : ""}`} type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick}>{icon}<span>{label}</span></button>;
}

function StyleMeter({ label, value }: { label: string; value: number }) {
  return <div className="room-style-meter"><span>{label}</span><div aria-label={`${label} ${value} / 5`}>{Array.from({ length: 5 }, (_, index) => <i className={index < value ? "filled" : ""} key={index} />)}</div><b>{value}</b></div>;
}
