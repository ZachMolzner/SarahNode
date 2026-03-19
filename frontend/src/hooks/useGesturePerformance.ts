import { useEffect, useMemo, useRef, useState } from "react";
import type { AvatarState } from "../types/avatar";
import { GestureController, type GesturePerformanceSnapshot } from "../lib/gestureController";

type GesturePerformanceInput = {
  avatarState: AvatarState;
  startupRequested: boolean;
  shutdownRequested: boolean;
  listeningStartedAtMs: number;
  replyStartedAtMs: number;
  speakingStartedAtMs: number;
  latestReplyText: string;
};

const DEFAULT_SNAPSHOT: GesturePerformanceSnapshot = {
  activeGesture: "none",
  tone: "warm",
  priority: 99,
  progress: 0,
  bodyLean: 0,
  headTilt: 0,
  headNod: 0,
  postureOpen: 0.1,
  shoulderSettle: 0,
  bobAccent: 0,
  bowDepth: 0,
  glowBoost: 0,
  expressionSoftness: 0.1,
  emphasisPulse: 0,
  isRecovering: false,
};

export function useGesturePerformance(input: GesturePerformanceInput): GesturePerformanceSnapshot {
  const controllerRef = useRef(new GestureController());
  const inputRef = useRef(input);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  useEffect(() => {
    const intervalId = window.setInterval(() => setTick((value) => value + 1), 90);
    return () => window.clearInterval(intervalId);
  }, []);

  return useMemo(() => {
    const latestInput = inputRef.current;
    if (!latestInput) return DEFAULT_SNAPSHOT;

    return controllerRef.current.update({
      nowMs: Date.now(),
      mode: latestInput.avatarState.mode,
      mood: latestInput.avatarState.mood,
      isSpeaking: latestInput.avatarState.isSpeaking,
      startupRequested: latestInput.startupRequested,
      shutdownRequested: latestInput.shutdownRequested,
      listeningStartedAtMs: latestInput.listeningStartedAtMs,
      replyStartedAtMs: latestInput.replyStartedAtMs,
      speakingStartedAtMs: latestInput.speakingStartedAtMs,
      latestReplyText: latestInput.latestReplyText,
    });
  }, [tick]);
}
