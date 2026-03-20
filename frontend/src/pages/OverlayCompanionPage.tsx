import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EventLog } from "../components/EventLog";
import { StatusCards } from "../components/StatusCards";
import { useEvents } from "../hooks/useEvents";
import {
  deleteMemoryItem,
  emitVoiceEvent,
  fetchAssistantState,
  fetchIdentityState,
  fetchMemoryItems,
  resetVoiceProfile,
  sendAssistantMessage,
  transcribeAudio,
  updateNicknamePolicy,
  type IdentityStateResponse,
  type MemoryItem,
} from "../lib/api";
import { AvatarPanel } from "../components/avatar/AvatarPanel";
import { useAvatarState } from "../hooks/useAvatarState";
import { VoiceRecorder } from "../components/voice/VoiceRecorder";
import { createAppShell } from "../lib/appShell";
import { OverlayController } from "../lib/overlayController";
import { isOverlayMode } from "../lib/displayMode";
import { isShutdownCancellation, isShutdownConfirmation, matchShutdownIntent } from "../lib/shutdownIntent";
import { runShutdownFlow } from "../lib/shutdownController";
import { SubtitleCaptions } from "../components/captions/SubtitleCaptions";
import { useGesturePerformance } from "../hooks/useGesturePerformance";
import { createVoiceOrchestrator, type TTSPlaybackPayload } from "../lib/voiceOrchestrator";
import { pickNonRepeatingLine } from "../lib/voiceLines";
import { SettingsPanel } from "../components/SettingsPanel";
import { WebAnswerTextbox, type WebAnswerRevealStage, type WebAnswerViewModel } from "../components/WebAnswerTextbox";
import { useSettingsStore } from "../hooks/useSettingsStore";
import { computeWebGroundedSignature, normalizeWebGroundedPayload } from "../lib/webGroundedAnswer";
import { resolveAvatarExpression } from "../lib/avatarExpressionResolver";
import { resolvePlatformProfile } from "../lib/platformProfile";

const EXPRESSION_REACTION_COOLDOWN_MS = {
  interrupted: 2400,
  error: 2800,
  groundedResult: 3600,
} as const;

const SEARCH_PRESENTATION_POLISH_MS = {
  textboxEnterDelay: 110,
  poseExitDelay: 170,
} as const;

const SEARCH_PRESENTATION_CUE_DEFAULTS = {
  noneAt: 0,
} as const;

type PresenceState = "idle" | "listening" | "thinking" | "speaking" | "presenting_search_results";

export function OverlayCompanionPage() {
  const adminEntryRequestedOnLaunch = useMemo(() => {
    if (typeof window === "undefined") return false;
    const search = new URLSearchParams(window.location.search);
    return search.get("admin") === "1" || search.get("settings") === "1" || search.get("debug") === "1";
  }, []);
  const { events, connectionState } = useEvents();
  const processedTtsKeyRef = useRef<string>("");
  const processedReplyKeyRef = useRef<string>("");
  const processedThinkingKeyRef = useRef<string>("");
  const processedErrorKeyRef = useRef<string>("");
  const startupLineRef = useRef<string | null>(null);
  const shutdownLineRef = useRef<string | null>(null);
  const lastSearchReactionAtRef = useRef(0);

  const [username, setUsername] = useState("zach");
  const [content, setContent] = useState("Give me a quick plan for today.");
  const [priority, setPriority] = useState(1);
  const [conversationMode, setConversationMode] = useState<"personal" | "shared">("personal");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [playbackAmplitude, setPlaybackAmplitude] = useState(0);
  const [mouthOpenAmount, setMouthOpenAmount] = useState(0);
  const [audioReady, setAudioReady] = useState(false);
  const [llmStatus, setLlmStatus] = useState("loading");
  const [ttsStatus, setTtsStatus] = useState("loading");
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);
  const [shutdownPendingConfirm, setShutdownPendingConfirm] = useState(false);
  const [shutdownPrompt, setShutdownPrompt] = useState<string | null>(null);
  const [shutdownStatus, setShutdownStatus] = useState<"idle" | "starting" | "ended">("idle");
  const [captionText, setCaptionText] = useState("");
  const [captionSpeaker, setCaptionSpeaker] = useState<"sarah" | "user" | null>(null);
  const [isCaptionVisible, setIsCaptionVisible] = useState(false);
  const [lastTranscriptAt, setLastTranscriptAt] = useState(0);
  const [lastUserSpeechAt, setLastUserSpeechAt] = useState(0);
  const [lastReplyAt, setLastReplyAt] = useState(0);
  const [sessionReadyAt, setSessionReadyAt] = useState(0);
  const [startupGreetingRequested, setStartupGreetingRequested] = useState(false);
  const [startupGreetingDelivered, setStartupGreetingDelivered] = useState(false);
  const [shutdownPerformanceDelivered, setShutdownPerformanceDelivered] = useState(false);
  const [listeningStartedAt, setListeningStartedAt] = useState(0);
  const [speakingStartedAt, setSpeakingStartedAt] = useState(0);
  const [webAnswer, setWebAnswer] = useState<WebAnswerViewModel | null>(null);
  const [isWebAnswerVisible, setIsWebAnswerVisible] = useState(false);
  const [isWebAnswerInteracting, setIsWebAnswerInteracting] = useState(false);
  const [hasExpandedSources, setHasExpandedSources] = useState(false);
  const [lastWebGroundedAt, setLastWebGroundedAt] = useState(0);
  const [summonedAt, setSummonedAt] = useState(0);
  const [interactionStartedAt, setInteractionStartedAt] = useState(0);
  const [searchStartedAt, setSearchStartedAt] = useState(0);
  const [sourceExpandedAt, setSourceExpandedAt] = useState(0);
  const [interruptedAt, setInterruptedAt] = useState(0);
  const [errorAt, setErrorAt] = useState(0);
  const [noResultAt, setNoResultAt] = useState(0);
  const [speakingEndedAt, setSpeakingEndedAt] = useState(0);
  const [identityState, setIdentityState] = useState<IdentityStateResponse | null>(null);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [profileRefreshError, setProfileRefreshError] = useState<string | null>(null);
  const [expressionClockMs, setExpressionClockMs] = useState(() => Date.now());
  const latestGroundedEventRef = useRef<string>("");
  const lastGroundedSignatureRef = useRef<string>("");
  const groundedDismissTimerRef = useRef<number | null>(null);
  const reactionCooldownRef = useRef({
    interrupted: 0,
    error: 0,
    groundedResult: 0,
  });
  const voiceOrchestratorRef = useRef(
    createVoiceOrchestrator({
      onCaption: (text) => {
        setCaptionSpeaker("sarah");
        setCaptionText(text);
      },
      onPlaybackStateChange: (isPlaying) => setIsAudioPlaying(isPlaying),
      onPlaybackAmplitudeChange: (amplitude) => setPlaybackAmplitude(amplitude),
    })
  );

  const stampReactionWithCooldown = useCallback((key: keyof typeof EXPRESSION_REACTION_COOLDOWN_MS, setter: (value: number) => void) => {
    const now = Date.now();
    if (now - reactionCooldownRef.current[key] < EXPRESSION_REACTION_COOLDOWN_MS[key]) return false;
    reactionCooldownRef.current[key] = now;
    setter(now);
    return true;
  }, []);

  const appShell = useMemo(() => createAppShell(), []);
  const { settings, settingsReady, settingsOpen, setSettingsOpen, updateSettings, windowBridge } = useSettingsStore();
  const platformProfile = useMemo(() => resolvePlatformProfile(windowBridge.isNativeDesktop), [windowBridge.isNativeDesktop]);
  const desktopFeaturesEnabled = windowBridge.isNativeDesktop;
  const displayMode = {
    ...appShell.displayMode,
    activeMode: desktopFeaturesEnabled ? (settings.overlayMode ? "overlay" : "immersive") : "immersive",
  };
  const overlayEnabled = isOverlayMode(displayMode);
  const [overlayControlsVisible, setOverlayControlsVisible] = useState(false);
  const overlayControllerRef = useRef<OverlayController | null>(null);
  const webPanelRegionRef = useRef<HTMLElement | null>(null);
  const totalEvents = useMemo(() => events.length, [events]);
  const latestReply = events.find((event) => event.type === "reply_selected")?.payload?.["text"];
  const baseAvatarState = useAvatarState(events);
  const isSpeaking = baseAvatarState.isSpeaking || isAudioPlaying;
  const isSearchPresentationActive = isWebAnswerVisible && isSpeaking;
  const [isSearchPresentationPoseActive, setIsSearchPresentationPoseActive] = useState(isSearchPresentationActive);
  const [isSearchTextboxVisible, setIsSearchTextboxVisible] = useState(isSearchPresentationActive);
  const [webAnswerRevealStage, setWebAnswerRevealStage] = useState<WebAnswerRevealStage>(0);
  const [searchHeadingRevealAt, setSearchHeadingRevealAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const [searchFindingsRevealAt, setSearchFindingsRevealAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const [searchRevealSettledAt, setSearchRevealSettledAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const searchPresentationTimersRef = useRef<{ textboxEnter: number | null; poseRelease: number | null }>({
    textboxEnter: null,
    poseRelease: null,
  });

  useEffect(() => {
    if (searchPresentationTimersRef.current.textboxEnter) {
      window.clearTimeout(searchPresentationTimersRef.current.textboxEnter);
      searchPresentationTimersRef.current.textboxEnter = null;
    }
    if (searchPresentationTimersRef.current.poseRelease) {
      window.clearTimeout(searchPresentationTimersRef.current.poseRelease);
      searchPresentationTimersRef.current.poseRelease = null;
    }

    if (isSearchPresentationActive) {
      setIsSearchPresentationPoseActive(true);
      searchPresentationTimersRef.current.textboxEnter = window.setTimeout(() => {
        setIsSearchTextboxVisible(true);
      }, SEARCH_PRESENTATION_POLISH_MS.textboxEnterDelay);
      return;
    }

    setIsSearchTextboxVisible(false);
    searchPresentationTimersRef.current.poseRelease = window.setTimeout(() => {
      setIsSearchPresentationPoseActive(false);
    }, SEARCH_PRESENTATION_POLISH_MS.poseExitDelay);
  }, [isSearchPresentationActive]);

  useEffect(() => {
    if (webAnswerRevealStage === 0) {
      setSearchHeadingRevealAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      setSearchFindingsRevealAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      setSearchRevealSettledAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      return;
    }
    const now = Date.now();
    if (webAnswerRevealStage >= 1 && searchHeadingRevealAt <= 0) setSearchHeadingRevealAt(now);
    if (webAnswerRevealStage >= 2 && searchFindingsRevealAt <= 0) setSearchFindingsRevealAt(now);
    if (webAnswerRevealStage >= 3 && searchRevealSettledAt <= 0) setSearchRevealSettledAt(now);
  }, [searchFindingsRevealAt, searchHeadingRevealAt, searchRevealSettledAt, webAnswerRevealStage]);

  useEffect(
    () => () => {
      if (searchPresentationTimersRef.current.textboxEnter) {
        window.clearTimeout(searchPresentationTimersRef.current.textboxEnter);
      }
      if (searchPresentationTimersRef.current.poseRelease) {
        window.clearTimeout(searchPresentationTimersRef.current.poseRelease);
      }
    },
    []
  );

  const presenceState: PresenceState =
    shutdownStatus === "starting" || shutdownStatus === "ended"
      ? "idle"
      : isSearchPresentationPoseActive
        ? "presenting_search_results"
        : isSpeaking
          ? "speaking"
          : baseAvatarState.mode === "listening"
            ? "listening"
            : baseAvatarState.mode === "thinking"
              ? "thinking"
              : "idle";
  const lastInteractionAt = Math.max(lastUserSpeechAt, lastReplyAt, listeningStartedAt, interactionStartedAt);
  const expressionState = resolveAvatarExpression({
    nowMs: expressionClockMs,
    mode: baseAvatarState.mode,
    isSpeaking,
    isPresenting: isWebAnswerVisible,
    isThinking: baseAvatarState.mode === "thinking",
    isListening: baseAvatarState.mode === "listening",
    isOverlayMode: overlayEnabled,
    isInteracting: isWebAnswerInteracting || isControlsOpen || isTranscriptOpen || settingsOpen,
    recentlyActiveMs: lastInteractionAt > 0 ? Math.max(0, expressionClockMs - lastInteractionAt) : Number.MAX_SAFE_INTEGER,
    summonedAtMs: summonedAt,
    interactionStartedAtMs: interactionStartedAt,
    listeningStartedAtMs: listeningStartedAt,
    searchStartedAtMs: searchStartedAt,
    groundedAnswerAtMs: lastWebGroundedAt,
    sourceExpandedAtMs: sourceExpandedAt,
    interruptedAtMs: interruptedAt,
    errorAtMs: errorAt,
    noResultAtMs: noResultAt,
    speakingEndedAtMs: speakingEndedAt,
  });
  const expressionDebugEnabled = typeof window !== "undefined" && window.location.search.includes("debugExpressions=1");
  const [audioNeedsGesture, setAudioNeedsGesture] = useState(false);
  const [adminSurfaceVisible, setAdminSurfaceVisible] = useState(() => adminEntryRequestedOnLaunch);
  const [isAvatarDragging, setIsAvatarDragging] = useState(false);
  const motionDebugEnabled = typeof window !== "undefined" && window.location.search.includes("debugMotion=1");

  const avatarState =
    shutdownStatus === "starting" || shutdownStatus === "ended"
      ? {
          ...baseAvatarState,
          mode: "shutting_down",
          mood: "goodbye",
          isSpeaking: false,
          mouthIntensity: 0.05,
          expression: "neutral",
          reaction: "none",
          expressionIntensity: 0.7,
        }
      : {
          ...baseAvatarState,
          mode:
            presenceState === "presenting_search_results"
              ? "presenting_search_results"
              : presenceState === "speaking"
                ? "talking"
                : baseAvatarState.mode,
          mood: expressionState.mood,
          isSpeaking,
          mouthIntensity: mouthOpenAmount,
          expression: expressionState.expression,
          reaction: expressionState.reaction,
          expressionIntensity: expressionState.intensity,
        };
  const latestReplyText = typeof latestReply === "string" ? latestReply : "";

  const gesturePerformance = useGesturePerformance({
    avatarState,
    startupRequested: startupGreetingRequested,
    shutdownRequested: shutdownStatus === "starting" || shutdownStatus === "ended",
    listeningStartedAtMs: listeningStartedAt,
    replyStartedAtMs: lastReplyAt,
    speakingStartedAtMs: speakingStartedAt,
    latestReplyText,
  });

  useEffect(() => {
    const id = window.setInterval(() => setExpressionClockMs(Date.now()), 120);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const timerId = window.setTimeout(() => {
      setSessionReadyAt(Date.now());
      setStartupGreetingRequested(true);
      setSummonedAt(Date.now());
    }, 850);
    return () => window.clearTimeout(timerId);
  }, []);

  useEffect(() => {
    if (startupGreetingDelivered || !startupGreetingRequested || !sessionReadyAt || shutdownStatus !== "idle") return;
    setStartupGreetingDelivered(true);
    const line = pickNonRepeatingLine("startup", startupLineRef.current);
    startupLineRef.current = line;
    void voiceOrchestratorRef.current.speakText(line, { context: "startup", mood: "cheerful" });
  }, [sessionReadyAt, shutdownStatus, startupGreetingDelivered, startupGreetingRequested]);

  useEffect(() => {
    return () => voiceOrchestratorRef.current.stopSpeaking();
  }, []);

  useEffect(() => {
    if (desktopFeaturesEnabled) return;
    const unlockAudio = async () => {
      const unlocked = await voiceOrchestratorRef.current.ensureAudioUnlockedFromGesture();
      setAudioNeedsGesture(!unlocked);
    };

    const handleUserGesture = () => {
      void unlockAudio();
    };

    window.addEventListener("pointerdown", handleUserGesture, { passive: true });
    return () => window.removeEventListener("pointerdown", handleUserGesture);
  }, [desktopFeaturesEnabled]);

  useEffect(() => {
    let frame = 0;
    let current = 0;
    const tick = () => {
      const target = isAudioPlaying ? Math.min(0.9, playbackAmplitude * 0.92) : 0;
      const smoothing = isAudioPlaying ? 0.42 : 0.2;
      current += (target - current) * smoothing;
      const next = isAudioPlaying ? Math.max(0, current) : current < 0.008 ? 0 : current;
      setMouthOpenAmount((prev) => (Math.abs(prev - next) > 0.01 || next === 0 ? next : prev));
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [isAudioPlaying, playbackAmplitude]);

  useEffect(() => {
    void fetchAssistantState()
      .then((state) => {
        const llm = state.providers?.llm;
        const tts = state.providers?.tts;
        setLlmStatus(`${llm?.active ?? "unknown"} (${llm?.mode ?? "unknown"})`);
        setTtsStatus(`${tts?.active ?? "unknown"} (${tts?.mode ?? "unknown"})`);
      })
      .catch(() => {
        setLlmStatus("unavailable");
        setTtsStatus("unavailable");
      });
  }, []);

  useEffect(() => {
    if (!adminSurfaceVisible) return;
    void refreshIdentityData();
  }, [adminSurfaceVisible, refreshIdentityData]);

  useEffect(() => {
    if (shutdownStatus !== "idle") return;
    const ttsEvent = events.find((event) => event.type === "tts_output");
    if (!ttsEvent) return;

    const ttsEventKey = `${ttsEvent.timestamp}-${JSON.stringify(ttsEvent.payload ?? {}).length}`;
    if (processedTtsKeyRef.current === ttsEventKey) {
      return;
    }
    processedTtsKeyRef.current = ttsEventKey;

    const payload = (ttsEvent.payload ?? {}) as TTSPlaybackPayload;
    const sourceText = typeof payload.source_text === "string" ? payload.source_text : "";
    if (!sourceText || !settings.voiceOutputEnabled) return;

    void voiceOrchestratorRef.current.speakText(sourceText, { ttsPayload: payload, context: "reply", mood: "warm" }).then(() => {
      const orchestrationStatus = voiceOrchestratorRef.current.getVoiceStatus();
      setAudioReady(orchestrationStatus.hasReplayableAudio);
      setTtsStatus(
        orchestrationStatus.backendProvider
          ? `${orchestrationStatus.backendProvider}${orchestrationStatus.backendModel ? ` · ${orchestrationStatus.backendModel}` : ""}${
              orchestrationStatus.backendVoice ? ` · ${orchestrationStatus.backendVoice}` : ""
            }`
          : orchestrationStatus.provider
      );
      setLastReplyAt(Date.now());
    });
  }, [events, settings.voiceOutputEnabled, shutdownStatus]);

  useEffect(() => {
    const replyEvent = events.find((event) => event.type === "reply_selected");
    if (!replyEvent) return;
    const replyText = replyEvent.payload?.["text"];
    if (typeof replyText !== "string" || !replyText.trim()) return;

    const replyKey = `${replyEvent.timestamp}-${replyText.length}`;
    if (processedReplyKeyRef.current === replyKey) return;
    processedReplyKeyRef.current = replyKey;

    setCaptionSpeaker("sarah");
    setCaptionText(replyText);
    setLastReplyAt(Date.now());
    window.setTimeout(() => {
      const latestTts = events.find((event) => event.type === "tts_output");
      const ttsSourceText = latestTts?.payload?.["source_text"];
      if (typeof ttsSourceText === "string" && ttsSourceText === replyText) return;
      if (!settings.voiceOutputEnabled) return;
      void voiceOrchestratorRef.current.speakText(replyText, { context: "reply", mood: "warm" });
    }, 450);
  }, [events, settings.voiceOutputEnabled]);

  const scheduleWebAnswerDismiss = useCallback(
    (delayMs: number) => {
      if (groundedDismissTimerRef.current) {
        window.clearTimeout(groundedDismissTimerRef.current);
      }

      groundedDismissTimerRef.current = window.setTimeout(() => {
        setIsWebAnswerVisible(false);
      }, delayMs);
    },
    []
  );

  useEffect(() => {
    return () => {
      if (groundedDismissTimerRef.current) {
        window.clearTimeout(groundedDismissTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const groundedEvent = events.find((event) => event.type === "web_grounded_answer");
    if (!groundedEvent) return;

    const eventKey = `${groundedEvent.timestamp}-${JSON.stringify(groundedEvent.payload ?? {}).length}`;
    if (latestGroundedEventRef.current === eventKey) return;
    latestGroundedEventRef.current = eventKey;

    const normalized = normalizeWebGroundedPayload({
      title: typeof groundedEvent.payload?.["title"] === "string" ? groundedEvent.payload["title"] : undefined,
      bullets: Array.isArray(groundedEvent.payload?.["bullets"])
        ? groundedEvent.payload["bullets"].filter((item): item is string => typeof item === "string")
        : undefined,
      sources: Array.isArray(groundedEvent.payload?.["sources"])
        ? groundedEvent.payload["sources"]
            .map((source) => {
              if (typeof source === "string") return source;
              if (!source || typeof source !== "object") return null;
              const title = (source as { title?: unknown }).title;
              const url = (source as { url?: unknown }).url;
              return {
                title: typeof title === "string" ? title : "",
                url: typeof url === "string" ? url : undefined,
              };
            })
            .filter((source): source is { title: string; url?: string } | string => Boolean(source))
        : undefined,
    });

    const signature = computeWebGroundedSignature(normalized);
    const identicalPayload = signature === lastGroundedSignatureRef.current;
    lastGroundedSignatureRef.current = signature;

    setWebAnswer({
      title: normalized.title,
      bullets: normalized.bullets,
      sources: normalized.sources,
      mode: overlayEnabled ? "overlay" : "immersive",
    });
    stampReactionWithCooldown("groundedResult", setLastWebGroundedAt);
    if (normalized.bullets.length === 0) {
      stampReactionWithCooldown("error", setNoResultAt);
    }
    setIsWebAnswerVisible(true);

    if (!identicalPayload && settings.voiceOutputEnabled) {
      const spoken = normalized.bullets.slice(0, 3).join(". ");
      if (spoken) {
        void voiceOrchestratorRef.current.speakText(`I checked the live web. ${spoken}`, { context: "reply", mood: "focused" });
      }
    }

    scheduleWebAnswerDismiss(identicalPayload ? 3600 : 7000);
  }, [events, overlayEnabled, scheduleWebAnswerDismiss, settings.voiceOutputEnabled, stampReactionWithCooldown]);

  useEffect(() => {
    if (!isWebAnswerVisible) return;
    scheduleWebAnswerDismiss(isSpeaking ? 7600 : 6200);
  }, [isSpeaking, isWebAnswerVisible, scheduleWebAnswerDismiss]);

  useEffect(() => {
    if (!isWebAnswerVisible || isSpeaking) return;
    scheduleWebAnswerDismiss(hasExpandedSources ? 5000 : 3600);
  }, [hasExpandedSources, isSpeaking, isWebAnswerVisible, scheduleWebAnswerDismiss]);

  useEffect(() => {
    const voiceEvent = events.find((event) => event.type.startsWith("voice:"));
    if (!voiceEvent) return;

    if (voiceEvent.type === "voice:recording_started") {
      setVoiceStatus("listening");
      setListeningStartedAt(Date.now());
    }
    if (voiceEvent.type === "voice:recording_stopped") setVoiceStatus("recording stopped");
    if (voiceEvent.type === "voice:transcribing") setVoiceStatus("transcribing");
    if (voiceEvent.type === "voice:transcribed") setVoiceStatus("transcribed");
    if (voiceEvent.type === "voice:error") setVoiceStatus("error");
  }, [events]);

  function stopAudioPlayback() {
    if (isSpeaking) stampReactionWithCooldown("interrupted", setInterruptedAt);
    voiceOrchestratorRef.current.stopSpeaking();
  }

  async function runConfirmedShutdown() {
    if (!shutdownPerformanceDelivered) {
      setShutdownPerformanceDelivered(true);
      const line = pickNonRepeatingLine("shutdown", shutdownLineRef.current);
      shutdownLineRef.current = line;
      await voiceOrchestratorRef.current.speakText(line, { context: "shutdown", mood: "goodbye" });
    }

    setShutdownStatus("starting");
    setShutdownPrompt("Closing session...");
    await new Promise((resolve) => window.setTimeout(resolve, 2200));

    const result = await runShutdownFlow({
      stopListening: () => setVoiceStatus("stopping"),
      stopAudio: stopAudioPlayback,
      stopAvatarSpeech: () => setIsAudioPlaying(false),
      appShell,
    });

    if (result === "fallback") {
      setShutdownStatus("ended");
      setShutdownPrompt("Session closed. You can now close this tab.");
      return;
    }

    setShutdownStatus("ended");
    setShutdownPrompt("Session closed.");
  }

  async function maybeHandleShutdownIntent(messageText: string): Promise<boolean> {
    if (shutdownStatus !== "idle") return true;

    if (shutdownPendingConfirm) {
      if (isShutdownConfirmation(messageText)) {
        setShutdownPendingConfirm(false);
        await runConfirmedShutdown();
        return true;
      }

      if (isShutdownCancellation(messageText)) {
        setShutdownPendingConfirm(false);
        setShutdownPrompt("Okay, keeping SarahNode open.");
        window.setTimeout(() => setShutdownPrompt(null), 2500);
        return true;
      }
    }

    const match = matchShutdownIntent(messageText);
    if (!match.matched) return false;

    if (match.requiresConfirmation) {
      setShutdownPendingConfirm(true);
      setShutdownPrompt("Are you sure you want me to close?");
      return true;
    }

    await runConfirmedShutdown();
    return true;
  }

  async function handleSend(messageText = content) {
    if (await maybeHandleShutdownIntent(messageText)) {
      return;
    }

    setIsSending(true);
    const now = Date.now();
    setInteractionStartedAt(now);
    setSearchStartedAt(now);
    setError(null);
    setIsWebAnswerVisible(false);

    try {
      await sendAssistantMessage({ username, content: messageText, priority, conversation_mode: conversationMode });
      setContent("");
    } catch (err) {
      stampReactionWithCooldown("error", setErrorAt);
      setError(err instanceof Error ? err.message : "Failed to send message to assistant.");
    } finally {
      setIsSending(false);
    }
  }

  async function replayAudio() {
    await voiceOrchestratorRef.current.replayLastAudio();
  }

  const refreshIdentityData = useCallback(async () => {
    try {
      setProfileRefreshError(null);
      const [identity, memory] = await Promise.all([fetchIdentityState(), fetchMemoryItems()]);
      setIdentityState(identity);
      setMemoryItems(memory);
    } catch (err) {
      setProfileRefreshError(err instanceof Error ? err.message : "Failed to load identity profile data.");
    }
  }, []);

  useEffect(() => {
    void appShell.configureWindowForDisplayMode();

    const controller = new OverlayController(displayMode);
    overlayControllerRef.current = controller;
    void controller.start();

    return () => {
      void controller.stop();
      overlayControllerRef.current = null;
    };
  }, [appShell, displayMode]);

  useEffect(() => {
    if (!overlayEnabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        setOverlayControlsVisible((visible) => !visible);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [overlayEnabled]);

  useEffect(() => {
    if (platformProfile.isMobileWeb) {
      setOverlayControlsVisible(true);
      setIsControlsOpen(true);
    }
  }, [platformProfile.isMobileWeb]);

  useEffect(() => {
    if (!overlayEnabled) return;
    setIsControlsOpen(false);
    setIsTranscriptOpen(false);
  }, [overlayEnabled]);

  useEffect(() => {
    if (adminSurfaceVisible) return;
    setSettingsOpen(false);
    setIsControlsOpen(false);
    setIsTranscriptOpen(false);
  }, [adminSurfaceVisible, setSettingsOpen]);

  useEffect(() => {
    if (!overlayEnabled || !overlayControlsVisible) return;
    setIsControlsOpen(true);
  }, [overlayControlsVisible, overlayEnabled]);

  useEffect(() => {
    if (!windowBridge.isNativeDesktop) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setAdminSurfaceVisible((visible) => !visible);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [windowBridge.isNativeDesktop]);

  useEffect(() => {
    if (!windowBridge.isNativeDesktop) return;
    let active = true;
    let cleanup = () => {};
    void windowBridge
      .onDesktopCommand((event) => {
        if (!active || event.command !== "summon-hotkey") return;
        const now = Date.now();
        setSummonedAt(now);
        setInteractionStartedAt(now);
      })
      .then((unlisten) => {
        cleanup = unlisten;
      });
    return () => {
      active = false;
      cleanup();
    };
  }, [windowBridge]);

  useEffect(() => {
    if (isSpeaking) {
      setSpeakingStartedAt((previous) => (Date.now() - previous > 320 ? Date.now() : previous));
    } else if (speakingStartedAt > 0) {
      setSpeakingEndedAt(Date.now());
    }
  }, [isSpeaking, speakingStartedAt]);

  useEffect(() => {
    const stateEvent = events.find((event) => event.type === "assistant_state");
    const assistantState = stateEvent?.payload?.["state"];
    const eventKey = stateEvent ? `${stateEvent.timestamp}-${String(assistantState ?? "")}` : "";
    if (!stateEvent || processedThinkingKeyRef.current === eventKey) return;
    processedThinkingKeyRef.current = eventKey;
    if (typeof assistantState === "string" && assistantState.toLowerCase() === "thinking") {
      const now = Date.now();
      if (now - lastSearchReactionAtRef.current < 1500) return;
      lastSearchReactionAtRef.current = now;
      setSearchStartedAt(now);
    }
  }, [events]);

  useEffect(() => {
    const errorEvent = events.find((event) => event.type === "error" || event.type === "voice:error");
    const eventKey = errorEvent ? `${errorEvent.timestamp}-${errorEvent.type}` : "";
    if (!errorEvent || processedErrorKeyRef.current === eventKey) return;
    processedErrorKeyRef.current = eventKey;
    if (errorEvent) {
      stampReactionWithCooldown("error", setErrorAt);
    }
  }, [events, stampReactionWithCooldown]);

  useEffect(() => {
    if (!overlayControllerRef.current) return;
    overlayControllerRef.current.setSecondaryInteractionRegion(webPanelRegionRef.current);
  }, [isWebAnswerVisible, webAnswer?.title]);

  useEffect(() => {
    if (!overlayControllerRef.current) return;
    void overlayControllerRef.current.setForceInteractive(isAvatarDragging || isWebAnswerInteracting);
  }, [isAvatarDragging, isWebAnswerInteracting]);

  useEffect(() => {
    setWebAnswer((current) => (current ? { ...current, mode: overlayEnabled ? "overlay" : "immersive" } : current));
  }, [overlayEnabled]);

  const showOverlayControls = adminSurfaceVisible && (!overlayEnabled || overlayControlsVisible || platformProfile.isMobileWeb);
  const shouldShowCaptions = adminSurfaceVisible;
  const bootstrappingDesktopSettings = windowBridge.isNativeDesktop && !settingsReady;

  if (bootstrappingDesktopSettings) {
    return <main style={pageStyle} />;
  }

  return (
    <main style={overlayEnabled ? overlayPageStyle : pageStyle}>
      <div style={overlayEnabled ? overlayStageStyle : stageStyle}>
        <AvatarPanel
          avatarState={avatarState}
          gesturePerformance={gesturePerformance}
          displayMode={displayMode}
          reducedEffects={platformProfile.reducedEffects}
          onInteractionRegionReady={(element) => overlayControllerRef.current?.setInteractionRegion(element)}
          onDragStateChange={setIsAvatarDragging}
          debugMotionEnabled={motionDebugEnabled}
          overlayVisibility={{
            controlsOpen: isControlsOpen,
            transcriptOpen: isTranscriptOpen,
            captionsVisible: isCaptionVisible,
            shutdownVisible: shutdownStatus !== "idle",
          }}
          presenceSignals={{
            transcriptEventAtMs: lastTranscriptAt,
            userSpokeAtMs: lastUserSpeechAt,
            replyAtMs: lastReplyAt,
            presentingAtMs: lastWebGroundedAt,
            searchHeadingRevealAtMs: searchHeadingRevealAt,
            searchFindingsRevealAtMs: searchFindingsRevealAt,
            searchSettledAtMs: searchRevealSettledAt,
          }}
        />
        {shouldShowCaptions ? (
          <SubtitleCaptions
            speaker={captionSpeaker}
            text={captionText}
            displayMode={displayMode.activeMode}
            onVisibilityChange={setIsCaptionVisible}
          />
        ) : null}

        {adminSurfaceVisible && overlayEnabled && !displayMode.nativeOverlayEnabled ? (
          <div style={browserOverlayWarningStyle}>Overlay visuals are active, but native click-through requires Tauri desktop mode.</div>
        ) : null}

        {showOverlayControls ? <div style={{ ...topOverlayStyle, gap: platformProfile.isPhoneLike ? 6 : 8 }}>
          <Pill label={`Connection: ${connectionState}`} muted={connectionState !== "open"} />
          <Pill label={`Voice: ${voiceStatus}`} muted={voiceStatus === "idle"} />
          <button type="button" onClick={() => setIsControlsOpen((open) => !open)} style={miniButtonStyle}>
            {isControlsOpen ? "Hide Controls" : "Menu"}
          </button>
          <button type="button" onClick={() => setIsTranscriptOpen((open) => !open)} style={miniButtonStyle}>
            {isTranscriptOpen ? "Hide Transcript" : "Transcript"}
          </button>
          <button type="button" onClick={() => setSettingsOpen((open) => !open)} style={miniButtonStyle}>
            {settingsOpen ? "Hide Settings" : "Settings"}
          </button>
        </div> : null}
        {expressionDebugEnabled ? (
          <div style={expressionDebugStyle}>
            baseline: {expressionState.debug.baseline} · reaction: {expressionState.reaction} · intensity:{" "}
            {expressionState.intensity.toFixed(2)} · gates:{" "}
            {[
              expressionState.debug.interruptionGateActive ? "interrupt" : null,
              expressionState.debug.speakingSettleActive ? "speak_settle" : null,
              expressionState.debug.errorRecoveryActive ? "error_recovery" : null,
            ]
              .filter(Boolean)
              .join(", ") || "none"}
          </div>
        ) : null}

        {showOverlayControls || shutdownPrompt ? (
          <div style={overlayEnabled ? overlayBottomOverlayStyle : bottomOverlayStyle}>
            {showOverlayControls ? (
              <VoiceRecorder
                disabled={isSending || shutdownStatus !== "idle"}
                shouldStop={shutdownStatus !== "idle"}
                onRecordingStarted={() => {
                  setVoiceStatus("listening");
                  setListeningStartedAt(Date.now());
                  setInteractionStartedAt(Date.now());
                  setIsWebAnswerVisible(false);
                  if (isSpeaking) stampReactionWithCooldown("interrupted", setInterruptedAt);
                  void emitVoiceEvent("voice:recording_started");
                }}
                onRecordingStopped={() => {
                  void emitVoiceEvent("voice:recording_stopped");
                }}
                onTranscribe={transcribeAudio}
                onTranscript={async (text) => {
                  setCaptionSpeaker("user");
                  setCaptionText(text);
                  setLastTranscriptAt(Date.now());
                  setLastUserSpeechAt(Date.now());
                  setContent(text);
                  await handleSend(text);
                }}
              />
            ) : null}
            {shutdownPrompt ? <p style={shutdownPromptStyle}>{shutdownPrompt}</p> : null}
          </div>
        ) : null}

        {showOverlayControls && isControlsOpen ? (
          <aside style={{ ...drawerStyle, width: platformProfile.isPhoneLike ? "calc(100vw - 16px)" : drawerStyle.width, right: platformProfile.isPhoneLike ? 8 : 10 }}>
            <h2 style={{ marginTop: 0 }}>Assistant Controls</h2>
            <div style={gridInputsStyle}>
              <label style={{ display: "grid", gap: 6 }}>
                <span>Username</span>
                <input value={username} onChange={(event) => setUsername(event.target.value)} style={inputStyle} />
              </label>

              <label style={{ display: "grid", gap: 6 }}>
                <span>Priority</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={priority}
                  onChange={(event) => setPriority(Number(event.target.value))}
                  style={inputStyle}
                />
              </label>

              <label style={{ display: "grid", gap: 6 }}>
                <span>Conversation mode</span>
                <select
                  value={conversationMode}
                  onChange={(event) => setConversationMode(event.target.value === "shared" ? "shared" : "personal")}
                  style={inputStyle}
                >
                  <option value="personal">Personal</option>
                  <option value="shared">Household shared</option>
                </select>
              </label>
            </div>

            <label style={{ display: "grid", gap: 6, marginTop: 12 }}>
              <span>Typed Message</span>
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={4}
                style={{ ...inputStyle, resize: "vertical", fontSize: platformProfile.isPhoneLike ? 16 : 14 }}
              />
            </label>

            <div style={submitRowStyle}>
              <button onClick={() => void handleSend()} disabled={isSending || !content.trim()} style={buttonStyle}>
                {isSending ? "Sending..." : "Send Message"}
              </button>
              <button onClick={replayAudio} disabled={!audioReady} style={secondaryButtonStyle}>
                Replay Last Audio
              </button>
            </div>

            {error ? <span style={{ color: "#ff8c8c" }}>{error}</span> : null}

            <div style={{ marginTop: 14, display: "grid", gap: 12 }}>
              <StatusCards
                events={events}
                connectionState={connectionState}
                isAudioPlaying={isAudioPlaying}
                llmStatus={llmStatus}
                ttsStatus={ttsStatus}
              />
            </div>
          </aside>
        ) : null}

        {showOverlayControls && isTranscriptOpen ? (
          <section style={{ ...transcriptOverlayStyle, width: platformProfile.isPhoneLike ? "calc(100vw - 16px)" : transcriptOverlayStyle.width, left: platformProfile.isPhoneLike ? 8 : 10 }}>
            <header style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
              <strong>Event Transcript</strong>
              <span style={{ opacity: 0.8, fontSize: 12 }}>Events: {totalEvents}</span>
            </header>
            <p style={{ margin: "8px 0 10px", fontSize: 12, opacity: 0.8 }}>
              Latest reply: {typeof latestReply === "string" ? latestReply : "No reply yet."}
            </p>
            <div style={{ maxHeight: "40vh", overflowY: "auto" }}>
              <EventLog events={events.slice(0, 20)} />
            </div>
          </section>
        ) : null}

        {adminSurfaceVisible ? (
          <SettingsPanel
            open={settingsOpen}
            settings={settings}
            desktopFeaturesEnabled={desktopFeaturesEnabled}
            onClose={() => setSettingsOpen(false)}
            onChange={(patch) => {
              void updateSettings(patch);
            }}
            onSummonNow={() => {
              setSummonedAt(Date.now());
              void windowBridge.summonWindow();
            }}
            identityState={identityState}
            memoryItems={memoryItems}
            profileRefreshError={profileRefreshError}
            onRefreshProfiles={() => {
              void refreshIdentityData();
            }}
            onToggleMamaNickname={(enabled) => {
              void updateNicknamePolicy(enabled).then(refreshIdentityData).catch((err) => {
                setProfileRefreshError(err instanceof Error ? err.message : "Failed to update nickname policy.");
              });
            }}
            onDeleteMemoryItem={(itemId) => {
              void deleteMemoryItem(itemId).then(refreshIdentityData).catch((err) => {
                setProfileRefreshError(err instanceof Error ? err.message : "Failed to delete memory item.");
              });
            }}
            onResetVoiceProfile={(profileId) => {
              void resetVoiceProfile(profileId).then(refreshIdentityData).catch((err) => {
                setProfileRefreshError(err instanceof Error ? err.message : "Failed to reset voice profile.");
              });
            }}
          />
        ) : null}

        <WebAnswerTextbox
          answer={webAnswer}
          visible={isSearchTextboxVisible}
          onRevealStageChange={setWebAnswerRevealStage}
          defaultCollapsedSources={settings.showSourceFooterCollapsed}
          onInteractionChange={setIsWebAnswerInteracting}
          onSourceExpansionChange={(expanded) => {
            setHasExpandedSources(expanded);
            if (expanded) setSourceExpandedAt(Date.now());
          }}
          onInteractionRegionReady={(element) => {
            webPanelRegionRef.current = element;
            overlayControllerRef.current?.setSecondaryInteractionRegion(element);
          }}
        />

        {adminSurfaceVisible && audioNeedsGesture ? <div style={audioGestureHintStyle}>Tap anywhere once to enable Sarah audio playback on this browser.</div> : null}

        {shutdownStatus === "ended" ? (
          <div style={shutdownOverlayStyle}>
            <h2 style={{ marginTop: 0 }}>Session closed</h2>
            <p style={{ marginBottom: 12 }}>{shutdownPrompt ?? "Session ended."}</p>
            <button type="button" onClick={() => window.close()} style={buttonStyle}>
              Try close tab
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function Pill({ label, muted = false }: { label: string; muted?: boolean }) {
  return <span style={{ ...pillStyle, opacity: muted ? 0.75 : 1 }}>{label}</span>;
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #0b1220 0%, #090f1a 100%)",
  color: "#f5f5f5",
  fontFamily: "Inter, Arial, sans-serif",
};

const stageStyle: React.CSSProperties = {
  width: "100%",
  minHeight: "100vh",
  position: "relative",
  overflow: "hidden",
  background: "radial-gradient(circle at 82% 20%, rgba(92, 128, 196, 0.12), transparent 36%)",
};

const overlayPageStyle: React.CSSProperties = {
  ...pageStyle,
  background: "transparent",
};

const overlayStageStyle: React.CSSProperties = {
  ...stageStyle,
  background: "transparent",
};

const browserOverlayWarningStyle: React.CSSProperties = {
  position: "absolute",
  top: 10,
  left: 10,
  padding: "6px 10px",
  borderRadius: 999,
  background: "rgba(16, 20, 36, 0.45)",
  border: "1px solid rgba(150, 170, 234, 0.35)",
  color: "rgba(244, 247, 255, 0.85)",
  fontSize: 11,
  zIndex: 18,
};

const topOverlayStyle: React.CSSProperties = {
  position: "absolute",
  top: 10,
  left: 10,
  right: 10,
  display: "flex",
  alignItems: "center",
  gap: 8,
  flexWrap: "wrap",
  zIndex: 15,
};

const bottomOverlayStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  right: 10,
  bottom: 10,
  display: "grid",
  gap: 8,
  maxWidth: 420,
  zIndex: 15,
};

const overlayBottomOverlayStyle: React.CSSProperties = {
  ...bottomOverlayStyle,
  maxWidth: 360,
};

const overlayHintStyle: React.CSSProperties = {
  position: "absolute",
  top: 10,
  right: 10,
  fontSize: 11,
  letterSpacing: 0.2,
  color: "rgba(245, 245, 255, 0.6)",
  zIndex: 16,
  pointerEvents: "none",
};

const expressionDebugStyle: React.CSSProperties = {
  position: "absolute",
  right: 10,
  top: 48,
  zIndex: 16,
  pointerEvents: "none",
  border: "1px solid rgba(132, 154, 214, 0.34)",
  borderRadius: 8,
  background: "rgba(7, 11, 20, 0.6)",
  color: "rgba(234, 240, 255, 0.88)",
  padding: "5px 9px",
  fontSize: 11,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  letterSpacing: 0.2,
  maxWidth: "min(70vw, 560px)",
};

const miniButtonStyle: React.CSSProperties = {
  border: "1px solid rgba(130, 155, 217, 0.55)",
  background: "rgba(9, 13, 26, 0.52)",
  color: "#eef1ff",
  borderRadius: 999,
  padding: "6px 12px",
  minHeight: 36,
  cursor: "pointer",
  backdropFilter: "blur(8px)",
};

const drawerStyle: React.CSSProperties = {
  position: "absolute",
  top: 54,
  right: 10,
  width: "min(500px, calc(100vw - 20px))",
  maxHeight: "calc(100vh - 64px)",
  overflowY: "auto",
  padding: 12,
  borderRadius: 14,
  background: "rgba(12, 18, 30, 0.76)",
  border: "1px solid rgba(118, 146, 215, 0.5)",
  backdropFilter: "blur(12px)",
  zIndex: 20,
};

const transcriptOverlayStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  bottom: 132,
  width: "min(560px, calc(100vw - 20px))",
  borderRadius: 12,
  padding: 10,
  border: "1px solid rgba(103, 125, 195, 0.5)",
  background: "rgba(6, 10, 18, 0.75)",
  zIndex: 20,
};

const shutdownOverlayStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "rgba(0, 0, 0, 0.65)",
  display: "grid",
  placeItems: "center",
  textAlign: "center",
  padding: 20,
  zIndex: 40,
};

const gridInputsStyle: React.CSSProperties = {
  display: "grid",
  gap: 12,
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
};

const submitRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  alignItems: "center",
  marginTop: 12,
  flexWrap: "wrap",
};

const inputStyle: React.CSSProperties = {
  border: "1px solid rgba(99, 116, 164, 0.9)",
  borderRadius: 10,
  padding: "10px 12px",
  background: "rgba(8, 12, 24, 0.88)",
  color: "#f5f5f5",
  fontSize: 14,
};

const buttonStyle: React.CSSProperties = {
  border: "1px solid rgba(206, 223, 255, 0.65)",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "rgba(222, 232, 255, 0.9)",
  color: "#0d162f",
  fontWeight: 700,
};

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid rgba(136, 155, 216, 0.75)",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "rgba(11, 16, 28, 0.66)",
  color: "#f5f5f5",
};

const audioGestureHintStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  right: 10,
  bottom: 86,
  zIndex: 16,
  borderRadius: 10,
  border: "1px solid rgba(143, 168, 230, 0.5)",
  background: "rgba(10, 16, 30, 0.76)",
  color: "#eff4ff",
  padding: "8px 10px",
  fontSize: 13,
};

const shutdownPromptStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.4,
  padding: "6px 10px",
  borderRadius: 8,
  border: "1px solid #2f3856",
  background: "rgba(7, 9, 16, 0.72)",
};

const pillStyle: React.CSSProperties = {
  border: "1px solid rgba(96, 121, 194, 0.62)",
  background: "rgba(8, 12, 22, 0.62)",
  borderRadius: 999,
  padding: "5px 10px",
  fontSize: 12,
  backdropFilter: "blur(8px)",
};
