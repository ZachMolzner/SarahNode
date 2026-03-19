export type VoiceLineBucket = "startup" | "listening" | "shutdown";

export const VOICE_LINE_POOLS: Record<VoiceLineBucket, readonly string[]> = {
  startup: [
    "Hi! I'm really happy to be here with you.",
    "Hey there. I'm ready whenever you are.",
    "Hello! It's great to see you again.",
  ],
  listening: ["Got it.", "I'm listening.", "Okay, I'm with you."],
  shutdown: ["Thank you for your time. Goodbye.", "Okay. I'll close things down now. Goodbye.", "Take care. I'll be here when you need me again."],
};

export function pickNonRepeatingLine(bucket: VoiceLineBucket, previousLine: string | null): string {
  const pool = VOICE_LINE_POOLS[bucket];
  if (pool.length === 0) return "";
  if (pool.length === 1 || !previousLine) return pool[0];

  const filtered = pool.filter((line) => line !== previousLine);
  const candidates = filtered.length > 0 ? filtered : [...pool];
  const nextIndex = Math.floor(Math.random() * candidates.length);
  return candidates[nextIndex] ?? pool[0];
}
