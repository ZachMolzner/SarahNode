import type { SemanticPresenceMode } from "./presenceController";

export type PresenceMode = "idle" | "listening" | "thinking" | "speaking" | "presenting_search_results";

type DerivePresenceModesInput = {
  shutdownStatus: "idle" | "starting" | "ended";
  isSearchPresentationPoseActive: boolean;
  isSpeaking: boolean;
  avatarMode: string;
  isWebAnswerVisible: boolean;
  nowMs: number;
  searchStartedAtMs: number;
  lastReplyAtMs: number;
  speakingEndedAtMs: number;
  followUpReadyWindowMs: number;
  searchWorkingWindowMs: number;
};

export function derivePresenceModes(input: DerivePresenceModesInput): {
  presenceMode: PresenceMode;
  semanticPresenceMode: SemanticPresenceMode;
} {
  const presenceMode: PresenceMode =
    input.shutdownStatus === "starting" || input.shutdownStatus === "ended"
      ? "idle"
      : input.isSearchPresentationPoseActive
        ? "presenting_search_results"
        : input.isSpeaking
          ? "speaking"
          : input.avatarMode === "listening"
            ? "listening"
            : input.avatarMode === "thinking"
              ? "thinking"
              : "idle";

  const semanticPresenceMode: SemanticPresenceMode =
    input.avatarMode === "thinking" && !input.isWebAnswerVisible && input.nowMs - input.searchStartedAtMs < input.searchWorkingWindowMs
      ? "searching_browsing"
      : input.isWebAnswerVisible && !input.isSpeaking
        ? "processing_results"
        : input.isSpeaking && !input.isWebAnswerVisible
          ? "direct_answering"
          : presenceMode === "idle" && input.nowMs - Math.max(input.lastReplyAtMs, input.speakingEndedAtMs) < input.followUpReadyWindowMs
            ? "waiting_follow_up"
            : "neutral";

  return { presenceMode, semanticPresenceMode };
}
