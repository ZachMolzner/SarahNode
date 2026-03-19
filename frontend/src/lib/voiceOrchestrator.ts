import { SARAH_VOICE_PROFILE, type VoiceMood } from "./voiceProfile";

export type TTSPlaybackPayload = {
  provider?: string;
  model?: string;
  voice_id?: string;
  voice_name?: string;
  mime_type?: string;
  audio_base64?: string;
  audio_url?: string;
  url?: string;
  source_text?: string;
};

export type SpeakOptions = {
  mood?: VoiceMood;
  ttsPayload?: TTSPlaybackPayload | null;
  captionText?: string;
  context?: "startup" | "listening" | "reply" | "shutdown";
};

export type VoiceStatus = {
  mode: "idle" | "playing_audio" | "speaking_fallback";
  provider: "elevenlabs" | "browser" | "none";
  usingFallback: boolean;
  browserVoiceName: string | null;
  backendProvider: string | null;
  backendVoice: string | null;
  backendModel: string | null;
  lastError: string | null;
  hasReplayableAudio: boolean;
  mobileAudioUnlocked: boolean;
};

type VoiceOrchestratorDeps = {
  onCaption: (text: string) => void;
  onPlaybackStateChange: (isPlaying: boolean) => void;
  onPlaybackAmplitudeChange?: (amplitude: number) => void;
  onDebugStatus?: (status: VoiceStatus) => void;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function canUseBrowserSpeech() {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
}

function normalizeAudioSource(payload: TTSPlaybackPayload): string | null {
  if (typeof payload.audio_url === "string" && payload.audio_url.trim()) return payload.audio_url;
  if (typeof payload.url === "string" && payload.url.trim()) return payload.url;

  if (typeof payload.audio_base64 === "string" && payload.audio_base64.trim()) {
    const mimeType = typeof payload.mime_type === "string" && payload.mime_type ? payload.mime_type : "audio/mpeg";
    return `data:${mimeType};base64,${payload.audio_base64}`;
  }

  return null;
}

function rankVoice(voice: SpeechSynthesisVoice): number {
  const name = voice.name.toLowerCase();
  const lang = voice.lang.toLowerCase();
  let score = 0;

  if (lang.startsWith("en")) score += 20;
  if (voice.localService) score += 12;
  if (voice.default) score += 8;
  if (/(female|woman|girl|samantha|victoria|allison|ava|aria|jenny|libby|zira|sonia|karen)/.test(name)) score += 16;
  if (/(soft|natural|friendly|bright|clear|young)/.test(name)) score += 7;
  if (/(male|man|david|mark|george|fred)/.test(name)) score -= 12;

  return score;
}

function pickPreferredBrowserVoice(): SpeechSynthesisVoice | null {
  if (!canUseBrowserSpeech()) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  const ranked = [...voices].sort((a, b) => rankVoice(b) - rankVoice(a));
  return ranked[0] ?? null;
}

export function createVoiceOrchestrator(deps: VoiceOrchestratorDeps) {
  let activeAudio: HTMLAudioElement | null = null;
  let activeUtterance: SpeechSynthesisUtterance | null = null;
  let replayAudioUrl: string | null = null;
  let audioContext: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let sourceNode: MediaElementAudioSourceNode | null = null;
  let analyserData: Uint8Array | null = null;
  let analyserFrame: number | null = null;

  const status: VoiceStatus = {
    mode: "idle",
    provider: "none",
    usingFallback: false,
    browserVoiceName: null,
    backendProvider: null,
    backendVoice: null,
    backendModel: null,
    lastError: null,
    hasReplayableAudio: false,
    mobileAudioUnlocked: false,
  };

  const notify = () => deps.onDebugStatus?.({ ...status });

  const emitAmplitude = (next: number) => deps.onPlaybackAmplitudeChange?.(clamp(next, 0, 1));

  const stopAmplitudeTracking = () => {
    if (analyserFrame !== null) {
      window.cancelAnimationFrame(analyserFrame);
      analyserFrame = null;
    }
    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch {
        // Keep teardown resilient across browser engines.
      }
      sourceNode = null;
    }
    if (analyser) {
      try {
        analyser.disconnect();
      } catch {
        // Keep teardown resilient across browser engines.
      }
      analyser = null;
    }
    analyserData = null;
    emitAmplitude(0);
  };

  const startAmplitudeTracking = async (audio: HTMLAudioElement) => {
    if (typeof window === "undefined" || typeof window.AudioContext === "undefined") {
      emitAmplitude(0);
      return;
    }

    stopAmplitudeTracking();
    audioContext = audioContext ?? new window.AudioContext();
    if (audioContext.state === "suspended") {
      await audioContext.resume().catch(() => null);
    }

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.06;
    analyserData = new Uint8Array(analyser.fftSize);

    sourceNode = audioContext.createMediaElementSource(audio);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    const tick = () => {
      if (!analyser || !analyserData) return;
      analyser.getByteTimeDomainData(analyserData);

      let sumSquares = 0;
      for (let i = 0; i < analyserData.length; i += 1) {
        const centered = (analyserData[i] - 128) / 128;
        sumSquares += centered * centered;
      }
      const rms = Math.sqrt(sumSquares / analyserData.length);
      const gated = Math.max(0, rms - 0.012);
      const normalized = clamp(gated * 5.2, 0, 1);
      emitAmplitude(normalized);

      analyserFrame = window.requestAnimationFrame(tick);
    };

    analyserFrame = window.requestAnimationFrame(tick);
  };

  const clearSpeaking = () => {
    status.mode = "idle";
    stopAmplitudeTracking();
    deps.onPlaybackStateChange(false);
    notify();
  };

  const stopSpeaking = () => {
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    stopAmplitudeTracking();

    if (canUseBrowserSpeech()) {
      window.speechSynthesis.cancel();
    }
    activeUtterance = null;
    clearSpeaking();
  };

  const replayLastAudio = async () => {
    if (!replayAudioUrl) return false;
    try {
      stopSpeaking();
      const audio = new Audio(replayAudioUrl);
      activeAudio = audio;
      const played = await new Promise<boolean>((resolve) => {
        let settled = false;
        const finalize = (result: boolean) => {
          if (settled) return;
          settled = true;
          resolve(result);
        };
        audio.onplaying = () => {
          status.mode = "playing_audio";
          status.provider = "elevenlabs";
          status.usingFallback = false;
          deps.onPlaybackStateChange(true);
          void startAmplitudeTracking(audio);
          notify();
        };
        audio.onended = () => {
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          finalize(true);
        };
        audio.onerror = () => {
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          finalize(false);
        };

        void audio.play().catch(() => {
          if (activeAudio === audio) activeAudio = null;
          status.lastError = "Audio playback blocked until a user tap unlocks audio.";
          clearSpeaking();
          finalize(false);
        });
      });
      return played;
    } catch {
      return false;
    }
  };

  const speakWithBrowserFallback = async (text: string, mood: VoiceMood) => {
    if (!canUseBrowserSpeech()) {
      status.lastError = "Browser speech synthesis unavailable";
      notify();
      return false;
    }

    const profile = SARAH_VOICE_PROFILE.browserFallback;
    const offset = SARAH_VOICE_PROFILE.moodOffsets[mood];
    const utterance = new SpeechSynthesisUtterance(text);
    activeUtterance = utterance;

    const selectedVoice = pickPreferredBrowserVoice();
    if (selectedVoice) {
      utterance.voice = selectedVoice;
      status.browserVoiceName = selectedVoice.name;
    }

    utterance.rate = clamp(profile.rate + offset.rateDelta, 0.8, 1.12);
    utterance.pitch = clamp(profile.pitch + offset.pitchDelta, 1.0, 1.42);
    utterance.volume = profile.volume;

    return await new Promise<boolean>((resolve) => {
      utterance.onstart = () => {
        status.mode = "speaking_fallback";
        status.provider = "browser";
        status.usingFallback = true;
        deps.onPlaybackStateChange(true);
        notify();
      };
      utterance.onend = () => {
        if (activeUtterance === utterance) activeUtterance = null;
        clearSpeaking();
        resolve(true);
      };
      utterance.onerror = () => {
        status.lastError = "Browser speech synthesis failed";
        if (activeUtterance === utterance) activeUtterance = null;
        clearSpeaking();
        resolve(false);
      };

      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });
  };

  const speakText = async (text: string, options: SpeakOptions = {}) => {
    const trimmed = text.trim();
    if (!trimmed) return false;

    deps.onCaption(options.captionText ?? trimmed);
    stopSpeaking();

    const mood = options.mood ?? "warm";
    const payload = options.ttsPayload ?? null;
    const normalizedProvider = typeof payload?.provider === "string" ? payload.provider.toLowerCase() : null;
    const audioSource = payload ? normalizeAudioSource(payload) : null;

    status.backendProvider = normalizedProvider;
    status.backendVoice = payload?.voice_name ?? payload?.voice_id ?? null;
    status.backendModel = payload?.model ?? null;

    if (audioSource && normalizedProvider === SARAH_VOICE_PROFILE.elevenLabs.provider) {
      const audio = new Audio(audioSource);
      activeAudio = audio;
      replayAudioUrl = audioSource;
      status.hasReplayableAudio = true;

      const played = await new Promise<boolean>((resolve) => {
        let settled = false;
        const finalize = (result: boolean) => {
          if (settled) return;
          settled = true;
          resolve(result);
        };
        audio.onplaying = () => {
          status.mode = "playing_audio";
          status.provider = "elevenlabs";
          status.usingFallback = false;
          deps.onPlaybackStateChange(true);
          void startAmplitudeTracking(audio);
          notify();
        };
        audio.onended = () => {
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          finalize(true);
        };
        audio.onerror = () => {
          status.lastError = "ElevenLabs audio playback failed";
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          finalize(false);
        };

        void audio.play().catch(() => {
          status.lastError = "ElevenLabs audio playback failed";
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          finalize(false);
        });
      });

      if (played) return true;
    }

    return speakWithBrowserFallback(trimmed, mood);
  };

  const ensureAudioUnlockedFromGesture = async () => {
    if (typeof window === "undefined" || typeof window.AudioContext === "undefined") {
      status.mobileAudioUnlocked = true;
      return true;
    }

    audioContext = audioContext ?? new window.AudioContext();
    if (audioContext.state === "suspended") {
      await audioContext.resume().catch(() => null);
    }

    status.mobileAudioUnlocked = audioContext.state === "running";
    notify();
    return status.mobileAudioUnlocked;
  };

  return {
    speakText,
    stopSpeaking,
    replayLastAudio,
    ensureAudioUnlockedFromGesture,
    getVoiceStatus: () => ({ ...status }),
  };
}
