import { useEffect, useRef, useState } from "react";

type VoiceRecorderState = "idle" | "recording" | "transcribing";

type VoiceRecorderProps = {
  disabled?: boolean;
  shouldStop?: boolean;
  onRecordingStarted?: () => void;
  onRecordingStopped?: () => void;
  onTranscript: (text: string) => Promise<void> | void;
  onTranscribe: (blob: Blob) => Promise<{ text: string }>;
};

export function VoiceRecorder({
  disabled = false,
  shouldStop = false,
  onRecordingStarted,
  onRecordingStopped,
  onTranscript,
  onTranscribe,
}: VoiceRecorderProps) {
  const [state, setState] = useState<VoiceRecorderState>("idle");
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (!shouldStop || state !== "recording") return;
    recorderRef.current?.stop();
    setState("transcribing");
  }, [shouldStop, state]);

  async function startRecording() {
    if (disabled || state !== "idle") return;
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setError("Recording failed. Please try again.");
        cleanupRecorder();
        setState("idle");
      };

      recorder.onstop = () => {
        onRecordingStopped?.();
        void handleRecordingStop();
      };

      recorder.start();
      setState("recording");
      onRecordingStarted?.();
    } catch {
      setError("Microphone permission was denied or unavailable.");
      cleanupRecorder();
      setState("idle");
    }
  }

  function stopRecording() {
    if (state !== "recording") return;
    recorderRef.current?.stop();
    setState("transcribing");
  }

  async function handleRecordingStop() {
    const mimeType = recorderRef.current?.mimeType || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });

    cleanupRecorder();

    if (!blob.size) {
      setError("No audio captured. Please try again.");
      setState("idle");
      return;
    }

    try {
      const result = await onTranscribe(blob);
      const transcript = result.text.trim();
      if (!transcript) {
        setError("No speech detected. Please try again.");
      } else {
        await onTranscript(transcript);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed.");
    } finally {
      setState("idle");
    }
  }

  function cleanupRecorder() {
    recorderRef.current = null;
    chunksRef.current = [];

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }

  const isRecording = state === "recording";
  const isTranscribing = state === "transcribing";

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <button
        type="button"
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled || isTranscribing}
        style={{
          border: "1px solid #575757",
          borderRadius: 10,
          padding: "10px 14px",
          cursor: disabled || isTranscribing ? "not-allowed" : "pointer",
          background: isRecording ? "#7a1313" : "#232323",
          color: "#f5f5f5",
          fontWeight: 700,
        }}
      >
        {isRecording ? "■ Stop Recording" : "🎙 Start Recording"}
      </button>

      <span style={{ fontSize: 13, opacity: 0.85 }}>
        Voice: {state === "idle" ? "idle" : state === "recording" ? "listening / recording" : "transcribing..."}
      </span>
      {error ? <span style={{ color: "#ff8c8c", fontSize: 13 }}>{error}</span> : null}
    </div>
  );
}
