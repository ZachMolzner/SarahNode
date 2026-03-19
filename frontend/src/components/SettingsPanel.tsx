import type { CSSProperties } from "react";
import type { UserSettings } from "../types/settings";
import type { IdentityStateResponse, MemoryItem } from "../lib/api";

type SettingsPanelProps = {
  open: boolean;
  settings: UserSettings;
  desktopFeaturesEnabled: boolean;
  onClose: () => void;
  onChange: (patch: Partial<UserSettings>) => void;
  onSummonNow: () => void;
  identityState: IdentityStateResponse | null;
  memoryItems: MemoryItem[];
  profileRefreshError: string | null;
  onRefreshProfiles: () => void;
  onToggleMamaNickname: (enabled: boolean) => void;
  onDeleteMemoryItem: (itemId: string) => void;
  onResetVoiceProfile: (profileId: string) => void;
};

export function SettingsPanel({
  open,
  settings,
  desktopFeaturesEnabled,
  onClose,
  onChange,
  onSummonNow,
  identityState,
  memoryItems,
  profileRefreshError,
  onRefreshProfiles,
  onToggleMamaNickname,
  onDeleteMemoryItem,
  onResetVoiceProfile,
}: SettingsPanelProps) {
  if (!open) return null;

  return (
    <aside style={panelStyle}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{desktopFeaturesEnabled ? "Desktop Settings" : "Client Settings"}</h3>
        <button type="button" style={closeButtonStyle} onClick={onClose}>
          Close
        </button>
      </header>

      <p style={hintStyle}>
        {desktopFeaturesEnabled
          ? "Overlay mode = desktop companion. Immersive mode = focused interaction mode."
          : "Mobile/web clients use companion-safe defaults and hide native desktop controls."}
      </p>

      {desktopFeaturesEnabled ? (
        <>
          <label style={rowStyle}>
            <span>Overlay companion mode</span>
            <input
              type="checkbox"
              checked={settings.overlayMode}
              onChange={(event) =>
                onChange({ overlayMode: event.target.checked, preferredMode: event.target.checked ? "overlay" : "immersive" })
              }
            />
          </label>

          <label style={rowStyle}>
            <span>Always on top</span>
            <input type="checkbox" checked={settings.alwaysOnTop} onChange={(event) => onChange({ alwaysOnTop: event.target.checked })} />
          </label>

          <label style={rowStyle}>
            <span>Hide to tray on close</span>
            <input
              type="checkbox"
              checked={settings.closeToTrayOnClose}
              onChange={(event) => onChange({ closeToTrayOnClose: event.target.checked })}
            />
          </label>
        </>
      ) : null}

      <label style={rowStyle}>
        <span>Voice output enabled</span>
        <input
          type="checkbox"
          checked={settings.voiceOutputEnabled}
          onChange={(event) => onChange({ voiceOutputEnabled: event.target.checked })}
        />
      </label>

      <label style={rowStyle}>
        <span>Collapse source footer by default</span>
        <input
          type="checkbox"
          checked={settings.showSourceFooterCollapsed}
          onChange={(event) => onChange({ showSourceFooterCollapsed: event.target.checked })}
        />
      </label>

      {desktopFeaturesEnabled ? (
        <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
          <small style={{ opacity: 0.74 }}>Summon hotkey: Ctrl+Shift+Space</small>
          <button type="button" onClick={onSummonNow} style={summonButtonStyle}>
            Summon Sarah now
          </button>
        </div>
      ) : null}

      <hr style={{ borderColor: "rgba(164, 180, 250, 0.25)", width: "100%" }} />
      <div style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong>Identity & Memory</strong>
          <button type="button" style={closeButtonStyle} onClick={onRefreshProfiles}>
            Refresh
          </button>
        </div>
        {profileRefreshError ? <small style={{ color: "#ffc1c1" }}>{profileRefreshError}</small> : null}
        {identityState ? (
          <>
            {identityState.profiles.map((profile) => (
              <div key={profile.id} style={{ padding: 8, border: "1px solid rgba(164, 180, 250, 0.25)", borderRadius: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{profile.display_name ?? profile.id}</div>
                <small>Address as: {profile.preferred_address ?? "there"}</small>
                <br />
                <small>Voice profile: {profile.voice_profile_id ?? "not enrolled"}</small>
                <div style={{ marginTop: 6 }}>
                  <button type="button" style={closeButtonStyle} onClick={() => onResetVoiceProfile(profile.id)}>
                    Reset voice
                  </button>
                </div>
              </div>
            ))}
            <label style={rowStyle}>
              <span>Allow Aleena “Mama” nickname</span>
              <input
                type="checkbox"
                checked={identityState.nickname_policy.aleena_mama_enabled}
                onChange={(event) => onToggleMamaNickname(event.target.checked)}
              />
            </label>
          </>
        ) : (
          <small>Loading identity profiles…</small>
        )}
        <div style={{ display: "grid", gap: 6 }}>
          <strong style={{ fontSize: 13 }}>Memory items ({memoryItems.length})</strong>
          {memoryItems.slice(0, 5).map((item) => (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", gap: 6, fontSize: 12 }}>
              <span>
                [{item.scope}/{item.source}] {item.key}: {item.value}
              </span>
              <button type="button" style={closeButtonStyle} onClick={() => onDeleteMemoryItem(item.id)}>
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

const panelStyle: CSSProperties = {
  position: "absolute",
  right: 12,
  top: 56,
  width: "min(360px, 92vw)",
  borderRadius: 14,
  background: "rgba(16, 20, 32, 0.9)",
  border: "1px solid rgba(164, 180, 250, 0.3)",
  padding: 12,
  color: "#f5f7ff",
  backdropFilter: "blur(12px)",
  zIndex: 40,
  display: "grid",
  gap: 8,
};

const closeButtonStyle: CSSProperties = {
  borderRadius: 8,
  border: "1px solid rgba(164, 180, 250, 0.35)",
  background: "rgba(34, 40, 66, 0.88)",
  color: "inherit",
  padding: "4px 10px",
};

const rowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: 14,
};

const hintStyle: CSSProperties = {
  margin: 0,
  fontSize: 12,
  opacity: 0.75,
};

const summonButtonStyle: CSSProperties = {
  borderRadius: 9,
  border: "1px solid rgba(152, 178, 255, 0.4)",
  background: "rgba(73, 91, 167, 0.55)",
  color: "inherit",
  padding: "8px 10px",
};
