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
};

type VoiceOrchestratorDeps = {
  onCaption: (text: string) => void;
  onPlaybackStateChange: (isPlaying: boolean) => void;
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
  let replayAudio: HTMLAudioElement | null = null;

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
  };

  const notify = () => deps.onDebugStatus?.({ ...status });

  const clearSpeaking = () => {
    status.mode = "idle";
    deps.onPlaybackStateChange(false);
    notify();
  };

  const stopSpeaking = () => {
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }

    if (canUseBrowserSpeech()) {
      window.speechSynthesis.cancel();
    }
    activeUtterance = null;
    clearSpeaking();
  };

  const replayLastAudio = async () => {
    if (!replayAudio) return false;
    try {
      replayAudio.currentTime = 0;
      await replayAudio.play();
      return true;
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
      replayAudio = audio;
      status.hasReplayableAudio = true;

      const played = await new Promise<boolean>((resolve) => {
        audio.onplaying = () => {
          status.mode = "playing_audio";
          status.provider = "elevenlabs";
          status.usingFallback = false;
          deps.onPlaybackStateChange(true);
          notify();
        };
        audio.onended = () => {
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          resolve(true);
        };
        audio.onerror = () => {
          status.lastError = "ElevenLabs audio playback failed";
          if (activeAudio === audio) activeAudio = null;
          clearSpeaking();
          resolve(false);
        };

        void audio.play().then(() => resolve(true)).catch(() => resolve(false));
      });

      if (played) return true;
    }

    return speakWithBrowserFallback(trimmed, mood);
  };

  return {
    speakText,
    stopSpeaking,
    replayLastAudio,
    getVoiceStatus: () => ({ ...status }),
  };
}
