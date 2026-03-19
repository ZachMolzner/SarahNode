export type VoiceMood = "neutral" | "cheerful" | "warm" | "calm" | "focused" | "goodbye";

export type ElevenLabsVoiceSettings = {
  /** Higher values keep delivery more consistent and less expressive. */
  stability: number;
  /** Higher values pull output closer to target voice identity. */
  similarity_boost: number;
  /** Adds expressive style intensity; keep low for natural assistant speech. */
  style: number;
  /** Enables extra post-processing loudness/presence boost in ElevenLabs. */
  use_speaker_boost: boolean;
};

export type BrowserFallbackSettings = {
  rate: number;
  pitch: number;
  volume: number;
};

export const SARAH_VOICE_PROFILE = {
  targetTone: ["warm", "youthful", "soft", "bright", "supportive", "gentle", "clear diction", "slightly airy"],
  lineStyleGuidance: "Friendly young AI companion. Never imitate copyrighted character voices.",
  elevenLabs: {
    provider: "elevenlabs",
    settings: {
      stability: 0.46,
      similarity_boost: 0.76,
      style: 0.18,
      use_speaker_boost: false,
    } satisfies ElevenLabsVoiceSettings,
  },
  browserFallback: {
    rate: 0.92,
    pitch: 1.3,
    volume: 1,
  } satisfies BrowserFallbackSettings,
  moodOffsets: {
    cheerful: { pitchDelta: 0.05, rateDelta: 0.03 },
    warm: { pitchDelta: 0.02, rateDelta: 0.01 },
    calm: { pitchDelta: -0.05, rateDelta: -0.03 },
    focused: { pitchDelta: -0.03, rateDelta: -0.01 },
    goodbye: { pitchDelta: -0.08, rateDelta: -0.04 },
    neutral: { pitchDelta: 0, rateDelta: 0 },
  },
} as const;
