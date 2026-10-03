const PREFERRED_VOICE_HINTS = [
  "Microsoft Aria",
  "Microsoft Jenny",
  "Microsoft Zira",
  "Aria",
  "Jenny",
  "Zira",
];

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

  utterance.rate = 1.02;
  utterance.pitch = 1.03;
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
