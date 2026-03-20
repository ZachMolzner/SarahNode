import type { SemanticPresenceMode } from "./presenceController";

export type PresenceSignals = {
  transcriptEventAtMs: number;
  userSpokeAtMs: number;
  replyAtMs: number;
  presentingAtMs: number;
  searchHeadingRevealAtMs: number;
  searchFindingsRevealAtMs: number;
  searchSourcesRevealAtMs: number;
  searchSettledAtMs: number;
  semanticPresenceMode: SemanticPresenceMode;
};
