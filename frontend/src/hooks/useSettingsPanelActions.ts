import { useCallback } from "react";
import { deleteMemoryItem, resetVoiceProfile, updateNicknamePolicy } from "../lib/api";
import type { UserSettings } from "../types/settings";

type UseSettingsPanelActionsArgs = {
  refreshIdentityData: () => Promise<void>;
  setProfileRefreshError: (value: string | null) => void;
  setSummonedAt: (value: number) => void;
  updateSettings: (patch: Partial<UserSettings>) => Promise<void>;
  windowBridge: {
    summonWindow: () => Promise<void>;
  };
};

export function useSettingsPanelActions({
  refreshIdentityData,
  setProfileRefreshError,
  setSummonedAt,
  updateSettings,
  windowBridge,
}: UseSettingsPanelActionsArgs) {
  const handleSettingsChange = useCallback(
    (patch: Partial<UserSettings>) => {
      void updateSettings(patch);
    },
    [updateSettings]
  );

  const handleSummonNow = useCallback(() => {
    setSummonedAt(Date.now());
    void windowBridge.summonWindow();
  }, [setSummonedAt, windowBridge]);

  const handleToggleMamaNickname = useCallback(
    (enabled: boolean) => {
      void updateNicknamePolicy(enabled).then(refreshIdentityData).catch((err) => {
        setProfileRefreshError(err instanceof Error ? err.message : "Failed to update nickname policy.");
      });
    },
    [refreshIdentityData, setProfileRefreshError]
  );

  const handleDeleteMemoryItem = useCallback(
    (itemId: string) => {
      void deleteMemoryItem(itemId).then(refreshIdentityData).catch((err) => {
        setProfileRefreshError(err instanceof Error ? err.message : "Failed to delete memory item.");
      });
    },
    [refreshIdentityData, setProfileRefreshError]
  );

  const handleResetVoiceProfile = useCallback(
    (profileId: string) => {
      void resetVoiceProfile(profileId).then(refreshIdentityData).catch((err) => {
        setProfileRefreshError(err instanceof Error ? err.message : "Failed to reset voice profile.");
      });
    },
    [refreshIdentityData, setProfileRefreshError]
  );

  return {
    handleSettingsChange,
    handleSummonNow,
    handleToggleMamaNickname,
    handleDeleteMemoryItem,
    handleResetVoiceProfile,
  };
}
