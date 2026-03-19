import type { AppShell, AppCloseAttemptResult } from "./appShell";

export type ShutdownControllerDeps = {
  stopListening: () => void;
  stopAudio: () => void;
  stopAvatarSpeech: () => void;
  appShell: AppShell;
};

export async function runShutdownFlow({
  stopListening,
  stopAudio,
  stopAvatarSpeech,
  appShell,
}: ShutdownControllerDeps): Promise<AppCloseAttemptResult> {
  stopListening();
  stopAudio();
  stopAvatarSpeech();
  return appShell.requestClose();
}
