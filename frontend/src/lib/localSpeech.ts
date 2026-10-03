const PREFERRED_VOICE_HINTS = [
  "Microsoft Aria",
  "Microsoft Jenny",
  "Microsoft Zira",
  "Aria",
  "Jenny",
  "Zira",
];

export type SarahEmojiMood = "happy" | "relaxed" | "sad" | "angry" | "surprised" | "concerned";

const HAPPY_EMOJI = [
  "😀", "😃", "😄", "😁", "😆", "😊", "😍", "🥰", "😘", "😎",
  "🤩", "🥳", "😂", "🤣", "❤️", "❤", "💕", "💖", "💗", "💓",
  "💞", "💝", "💘", "🩷", "🧡", "💛", "💚", "💙", "💜", "🤍",
];

const RELAXED_EMOJI = [
  "🙂", "😌", "😅", "😉", "🤗", "☺", "☺️", "✨",
];

const SAD_EMOJI = [
  "😢", "😭", "😞", "😔", "😟", "😥", "🥺", "💔",
];

const ANGRY_EMOJI = [
  "😠", "😡", "🤬", "👿", "💢",
];

const SURPRISED_EMOJI = [
  "😮", "😯", "😲", "🤯", "😦",
];

const CONCERNED_EMOJI = [
  "😨", "😰", "😱", "😬", "😳", "😓", "⚠", "⚠️",
];

const EMOJI_SEQUENCE_RE =
  /\p{Extended_Pictographic}(?:\uFE0F|\uFE0E)?(?:\p{Emoji_Modifier})?(?:\u200D\p{Extended_Pictographic}(?:\uFE0F|\uFE0E)?(?:\p{Emoji_Modifier})?)*/gu;

export function emotionFromEmoji(text: string): SarahEmojiMood | null {
  if (ANGRY_EMOJI.some((emoji) => text.includes(emoji))) return "angry";
  if (SURPRISED_EMOJI.some((emoji) => text.includes(emoji))) return "surprised";
  if (CONCERNED_EMOJI.some((emoji) => text.includes(emoji))) return "concerned";
  if (SAD_EMOJI.some((emoji) => text.includes(emoji))) return "sad";
  if (HAPPY_EMOJI.some((emoji) => text.includes(emoji))) return "happy";
  if (RELAXED_EMOJI.some((emoji) => text.includes(emoji))) return "relaxed";
  return null;
}

export function stripEmojiForSpeech(text: string): string {
  return text
    .replace(EMOJI_SEQUENCE_RE, " ")
    .replace(/[\uFE0E\uFE0F\u200D]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function speechTextFromMarkdown(markdown: string): string {
  let text = markdown;

  text = text.replace(/\`\`\`[\s\S]*?\`\`\`/g, " I included a code example in the chat. ");
  text = text.replace(/!\[[^\]]*\]\([^)]*\)/g, " ");
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  text = text.replace(/https?:\/\/\S+/g, " link ");
  text = text.replace(/^#{1,6}\s+/gm, "");
  text = text.replace(/^\s*[-*+]\s+/gm, "");
  text = text.replace(/^\s*\d+[.)]\s+/gm, "");
  text = text.replace(/\*\*([^*]+)\*\*/g, "$1");
  text = text.replace(/__([^_]+)__/g, "$1");
  text = text.replace(/\`([^\`]+)\`/g, "$1");
  text = text.replace(/[>*_~]/g, "");
  text = stripEmojiForSpeech(text);
  text = text.replace(/\s+/g, " ").trim();

  const maxCharacters = 1800;
  if (text.length > maxCharacters) {
    const shortened = text.slice(0, maxCharacters);
    const sentenceEnd = Math.max(
      shortened.lastIndexOf("."),
      shortened.lastIndexOf("!"),
      shortened.lastIndexOf("?"),
    );
    const cutoff = sentenceEnd > 900 ? sentenceEnd + 1 : maxCharacters;
    return (
      shortened.slice(0, cutoff).trim() +
      " I've put the rest of the answer in the chat."
    );
  }

  return text;
}

function preferredConfiguredVoice(): string {
  return import.meta.env.VITE_SARAH_VOICE_NAME?.trim() ?? "";
}

export function chooseSarahVoice(
  voices: SpeechSynthesisVoice[],
): SpeechSynthesisVoice | null {
  if (!voices.length) return null;

  const configured = preferredConfiguredVoice().toLowerCase();
  if (configured) {
    const configuredMatch = voices.find((voice) =>
      voice.name.toLowerCase().includes(configured),
    );
    if (configuredMatch) return configuredMatch;
  }

  const localEnglishVoices = voices.filter(
    (voice) =>
      voice.localService && voice.lang.toLowerCase().startsWith("en"),
  );

  for (const hint of PREFERRED_VOICE_HINTS) {
    const match = localEnglishVoices.find((voice) =>
      voice.name.toLowerCase().includes(hint.toLowerCase()),
    );
    if (match) return match;
  }

  return (
    localEnglishVoices.find(
      (voice) => voice.lang.toLowerCase() === "en-us",
    ) ??
    localEnglishVoices[0] ??
    voices.find((voice) => voice.lang.toLowerCase() === "en-us") ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith("en")) ??
    voices[0] ??
    null
  );
}

export type LocalSpeechCallbacks = {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: () => void;
};

export function localSpeechSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof SpeechSynthesisUtterance !== "undefined"
  );
}

export function stopLocalSpeech(): void {
  if (!localSpeechSupported()) return;
  window.speechSynthesis.cancel();
}

export function speakSarahReply(
  markdown: string,
  callbacks: LocalSpeechCallbacks = {},
): boolean {
  if (!localSpeechSupported()) return false;

  const text = speechTextFromMarkdown(markdown);
  if (!text) return false;

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  const voice = chooseSarahVoice(window.speechSynthesis.getVoices());
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  } else {
    utterance.lang = "en-US";
  }

  const emojiMood = emotionFromEmoji(markdown);
  const prosody = {
    happy: { rate: 1.04, pitch: 1.08 },
    relaxed: { rate: 0.98, pitch: 1.01 },
    sad: { rate: 0.93, pitch: 0.95 },
    angry: { rate: 1.0, pitch: 0.96 },
    surprised: { rate: 1.06, pitch: 1.11 },
    concerned: { rate: 0.96, pitch: 0.98 },
  } as const;
  const selectedProsody = emojiMood ? prosody[emojiMood] : null;

  utterance.rate = selectedProsody?.rate ?? 1.02;
  utterance.pitch = selectedProsody?.pitch ?? 1.03;
  utterance.volume = 1.0;

  utterance.onstart = () => callbacks.onStart?.();
  utterance.onend = () => callbacks.onEnd?.();
  utterance.onerror = () => {
    callbacks.onError?.();
    callbacks.onEnd?.();
  };

  window.speechSynthesis.speak(utterance);
  return true;
}
