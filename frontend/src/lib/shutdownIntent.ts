export type ShutdownIntentMatch = {
  matched: boolean;
  requiresConfirmation: boolean;
  phrase?: string;
};

const EXPLICIT_SHUTDOWN_PHRASES = [
  "sarah close program",
  "sarah close the program",
  "sarah shut down",
  "sarah exit",
  "close sarahnode",
];

const HARD_SHUTDOWN_PHRASES = ["sarah shut down now", "sarah exit now", "close sarahnode now"];

const CONFIRMATION_PHRASES = ["yes", "confirm", "yes confirm", "do it", "close it"];
const CANCEL_PHRASES = ["no", "cancel", "stop", "never mind", "dont close", "do not close"];

export const SUPPORTED_SHUTDOWN_PHRASES = [...EXPLICIT_SHUTDOWN_PHRASES];

export function normalizeTranscript(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function matchShutdownIntent(rawTranscript: string): ShutdownIntentMatch {
  const transcript = normalizeTranscript(rawTranscript);
  const hardPhrase = HARD_SHUTDOWN_PHRASES.find((phrase) => transcript.includes(phrase));
  if (hardPhrase) {
    return { matched: true, phrase: hardPhrase, requiresConfirmation: false };
  }

  const phrase = EXPLICIT_SHUTDOWN_PHRASES.find((candidate) => transcript.includes(candidate));
  if (!phrase) {
    return { matched: false, requiresConfirmation: true };
  }

  return {
    matched: true,
    phrase,
    requiresConfirmation: true,
  };
}

export function isShutdownConfirmation(rawTranscript: string): boolean {
  const transcript = normalizeTranscript(rawTranscript);
  return CONFIRMATION_PHRASES.some((phrase) => transcript === phrase || transcript.includes(` ${phrase}`));
}

export function isShutdownCancellation(rawTranscript: string): boolean {
  const transcript = normalizeTranscript(rawTranscript);
  return CANCEL_PHRASES.some((phrase) => transcript === phrase || transcript.includes(phrase));
}
