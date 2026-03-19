use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::menu::{CheckMenuItemBuilder, MenuBuilder, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Listener, Manager, State, WebviewWindow};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

const SETTINGS_FILE_NAME: &str = "desktop-settings.json";
const SUMMON_SHORTCUT: &str = "Ctrl+Shift+Space";
const TRAY_ID: &str = "main-tray";

const MENU_SHOW_HIDE: &str = "show_hide";
const MENU_ALWAYS_ON_TOP: &str = "always_on_top";
const MENU_OVERLAY_MODE: &str = "overlay_mode";
const MENU_CLOSE_TO_TRAY: &str = "close_to_tray";
const MENU_QUIT: &str = "quit";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopSettings {
    #[serde(default = "default_true")]
    always_on_top: bool,
    #[serde(default = "default_true")]
    overlay_mode: bool,
    #[serde(default = "default_true")]
    close_to_tray_on_close: bool,
    #[serde(default = "default_true")]
    voice_output_enabled: bool,
    #[serde(default = "default_settings_version")]
    version: u32,
}

const CURRENT_SETTINGS_VERSION: u32 = 1;

const fn default_true() -> bool {
    true
}

const fn default_settings_version() -> u32 {
    CURRENT_SETTINGS_VERSION
}

impl Default for DesktopSettings {
    fn default() -> Self {
        Self {
            always_on_top: true,
            overlay_mode: true,
            close_to_tray_on_close: true,
            voice_output_enabled: true,
            version: CURRENT_SETTINGS_VERSION,
        }
    }
}

struct DesktopSettingsState {
    settings: Mutex<DesktopSettings>,
}

fn settings_path(app: &AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|dir| dir.join(SETTINGS_FILE_NAME))
}

fn normalize_settings(mut settings: DesktopSettings) -> DesktopSettings {
    if settings.version != CURRENT_SETTINGS_VERSION {
        settings.version = CURRENT_SETTINGS_VERSION;
    }
    settings
}

fn load_settings_from_disk(app: &AppHandle) -> DesktopSettings {
    let Some(path) = settings_path(app) else {
        return DesktopSettings::default();
    };

    match fs::read_to_string(path) {
        Ok(raw) => serde_json::from_str::<DesktopSettings>(&raw)
            .map(normalize_settings)
            .unwrap_or_default(),
        Err(_) => DesktopSettings::default(),
    }
}

fn save_settings_to_disk(app: &AppHandle, settings: &DesktopSettings) {
    let Some(path) = settings_path(app) else {
        return;
    };

    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }

    if let Ok(json) = serde_json::to_string_pretty(settings) {
        let _ = fs::write(path, json);
    }
}

fn with_main_window<F>(app: &AppHandle, mut callback: F) -> tauri::Result<()>
where
    F: FnMut(&WebviewWindow) -> tauri::Result<()>,
{
    if let Some(window) = app.get_webview_window("main") {
        callback(&window)?;
    }
    Ok(())
}

fn is_main_window_visible(app: &AppHandle) -> bool {
    with_main_window(app, |window| {
        let _ = window.is_visible()?;
        Ok(())
    })
    .is_ok()
        && app
            .get_webview_window("main")
            .and_then(|window| window.is_visible().ok())
            .unwrap_or(false)
}

fn apply_window_profile(app: &AppHandle, settings: &DesktopSettings) -> tauri::Result<()> {
    with_main_window(app, |window| {
        window.set_always_on_top(settings.always_on_top)?;
        window.set_fullscreen(!settings.overlay_mode)?;
        window.set_decorations(!settings.overlay_mode)?;
        Ok(())
    })
}

fn emit_desktop_settings(app: &AppHandle, settings: &DesktopSettings) {
    let _ = app.emit("desktop://settings-updated", settings);
}

fn emit_desktop_command(app: &AppHandle, command: &str) {
    let _ = app.emit(
        "desktop://command",
        serde_json::json!({
            "command": command,
        }),
    );
}

fn refresh_tray_state(app: &AppHandle) {
    let snapshot = app
        .state::<DesktopSettingsState>()
        .settings
        .lock()
        .map(|guard| guard.clone())
        .unwrap_or_default();

    let visible = is_main_window_visible(app);
    let show_hide_label = if visible { "Hide Sarah" } else { "Show Sarah" };

    if let Some(tray) = app.tray_by_id(TRAY_ID) {
        if let Some(item) = tray.menu().and_then(|menu| menu.get(MENU_SHOW_HIDE)) {
            let _ = item
                .as_menuitem()
                .map(|menu_item| menu_item.set_text(show_hide_label));
        }

        if let Some(item) = tray.menu().and_then(|menu| menu.get(MENU_ALWAYS_ON_TOP)) {
            let _ = item
                .as_check_menuitem()
                .map(|menu_item| menu_item.set_checked(snapshot.always_on_top));
        }

        if let Some(item) = tray.menu().and_then(|menu| menu.get(MENU_OVERLAY_MODE)) {
            let _ = item
                .as_check_menuitem()
                .map(|menu_item| menu_item.set_checked(snapshot.overlay_mode));
        }

        if let Some(item) = tray.menu().and_then(|menu| menu.get(MENU_CLOSE_TO_TRAY)) {
            let _ = item
                .as_check_menuitem()
                .map(|menu_item| menu_item.set_checked(snapshot.close_to_tray_on_close));
        }
    }
}

fn show_main_window(app: &AppHandle) {
    let _ = with_main_window(app, |window| {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        Ok(())
    });
    refresh_tray_state(app);
}

fn hide_main_window_internal(app: &AppHandle) {
    let _ = with_main_window(app, |window| {
        window.hide()?;
        Ok(())
    });
    refresh_tray_state(app);
}

fn toggle_window_visibility(app: &AppHandle) {
    let _ = with_main_window(app, |window| {
        if window.is_visible()? {
            window.hide()?;
        } else {
            let _ = window.unminimize();
            let _ = window.show();
            let _ = window.set_focus();
        }
        Ok(())
    });
    refresh_tray_state(app);
}

fn set_settings(
    app: &AppHandle,
    state: &State<'_, DesktopSettingsState>,
    settings: DesktopSettings,
) -> Result<DesktopSettings, String> {
    let normalized = normalize_settings(settings);
    {
        let mut guard = state
            .settings
            .lock()
            .map_err(|_| "failed to update desktop settings".to_string())?;
        *guard = normalized.clone();
    }

    apply_window_profile(app, &normalized).map_err(|err| err.to_string())?;
    save_settings_to_disk(app, &normalized);
    emit_desktop_settings(app, &normalized);
    refresh_tray_state(app);

    Ok(normalized)
}

#[tauri::command]
fn get_desktop_settings(state: State<'_, DesktopSettingsState>) -> Result<DesktopSettings, String> {
    state
        .settings
        .lock()
        .map(|guard| guard.clone())
        .map_err(|_| "failed to read desktop settings".to_string())
}

#[tauri::command]
fn update_desktop_settings(
    app: AppHandle,
    state: State<'_, DesktopSettingsState>,
    settings: DesktopSettings,
) -> Result<DesktopSettings, String> {
    set_settings(&app, &state, settings)
}

#[tauri::command]
fn summon_main_window(app: AppHandle) {
    show_main_window(&app);
}

#[tauri::command]
fn hide_main_window(app: AppHandle) {
    hide_main_window_internal(&app);
}

#[tauri::command]
fn toggle_always_on_top(
    app: AppHandle,
    state: State<'_, DesktopSettingsState>,
    enabled: bool,
) -> Result<DesktopSettings, String> {
    let mut settings = state
        .settings
        .lock()
        .map_err(|_| "failed to update always-on-top".to_string())?
        .clone();
    settings.always_on_top = enabled;
    set_settings(&app, &state, settings)
}

#[tauri::command]
fn set_overlay_mode(
    app: AppHandle,
    state: State<'_, DesktopSettingsState>,
    enabled: bool,
) -> Result<DesktopSettings, String> {
    let mut settings = state
        .settings
        .lock()
        .map_err(|_| "failed to update overlay mode".to_string())?
        .clone();
    settings.overlay_mode = enabled;
    set_settings(&app, &state, settings)
}

#[tauri::command]
fn set_close_to_tray_on_close(
    app: AppHandle,
    state: State<'_, DesktopSettingsState>,
    enabled: bool,
) -> Result<DesktopSettings, String> {
    let mut settings = state
        .settings
        .lock()
        .map_err(|_| "failed to update close-to-tray setting".to_string())?
        .clone();
    settings.close_to_tray_on_close = enabled;
    set_settings(&app, &state, settings)
}

fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let state = app.state::<DesktopSettingsState>();
    let snapshot = state
        .settings
        .lock()
        .map(|guard| guard.clone())
        .unwrap_or_default();
    let show_hide_label = if is_main_window_visible(app) {
        "Hide Sarah"
    } else {
        "Show Sarah"
    };

    let show_hide_item = MenuItemBuilder::new(show_hide_label)
        .id(MENU_SHOW_HIDE)
        .build(app)?;
    let always_on_top_item = CheckMenuItemBuilder::new("Always on top")
        .id(MENU_ALWAYS_ON_TOP)
        .checked(snapshot.always_on_top)
        .build(app)?;
    let overlay_mode_item = CheckMenuItemBuilder::new("Overlay mode")
        .id(MENU_OVERLAY_MODE)
        .checked(snapshot.overlay_mode)
        .build(app)?;
    let close_to_tray_item = CheckMenuItemBuilder::new("Hide on close (tray)")
        .id(MENU_CLOSE_TO_TRAY)
        .checked(snapshot.close_to_tray_on_close)
        .build(app)?;
    let quit_item = MenuItemBuilder::new("Quit SarahNode")
        .id(MENU_QUIT)
        .build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&show_hide_item)
        .separator()
        .item(&always_on_top_item)
        .item(&overlay_mode_item)
        .item(&close_to_tray_item)
        .separator()
        .item(&quit_item)
        .build()?;

    TrayIconBuilder::new()
        .id(TRAY_ID)
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                toggle_window_visibility(&tray.app_handle());
            }
        })
        .on_menu_event(|app, event| {
            let state = app.state::<DesktopSettingsState>();
            match event.id().as_ref() {
                MENU_SHOW_HIDE => toggle_window_visibility(app),
                MENU_ALWAYS_ON_TOP => {
                    let next = state
                        .settings
                        .lock()
                        .map(|guard| !guard.always_on_top)
                        .unwrap_or(true);
                    let _ = toggle_always_on_top(app.clone(), state, next);
                }
                MENU_OVERLAY_MODE => {
                    let next = state
                        .settings
                        .lock()
                        .map(|guard| !guard.overlay_mode)
                        .unwrap_or(true);
                    let _ = set_overlay_mode(app.clone(), state, next);
                }
                MENU_CLOSE_TO_TRAY => {
                    let next = state
                        .settings
                        .lock()
                        .map(|guard| !guard.close_to_tray_on_close)
                        .unwrap_or(true);
                    let _ = set_close_to_tray_on_close(app.clone(), state, next);
                }
                MENU_QUIT => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)?;

    refresh_tray_state(app);
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let initial_settings = load_settings_from_disk(&app.handle());
            app.manage(DesktopSettingsState {
                settings: Mutex::new(initial_settings.clone()),
            });

            apply_window_profile(&app.handle(), &initial_settings)?;
            save_settings_to_disk(&app.handle(), &initial_settings);
            setup_tray(&app.handle())?;

            let shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);
            let app_handle = app.handle().clone();
            app.global_shortcut()
                .on_shortcut(shortcut, move |_app, _shortcut, event| {
                    if event.state() == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                        show_main_window(&app_handle);
                        emit_desktop_command(&app_handle, "summon-hotkey");
                    }
                })?;

            let close_handle = app.handle().clone();
            if let Some(main_window) = app.get_webview_window("main") {
                main_window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        let should_hide = close_handle
                            .state::<DesktopSettingsState>()
                            .settings
                            .lock()
                            .map(|guard| guard.close_to_tray_on_close)
                            .unwrap_or(true);

                        if should_hide {
                            api.prevent_close();
                            hide_main_window_internal(&close_handle);
                            emit_desktop_command(&close_handle, "hidden-to-tray");
                        }
                    }
                });
            }

            let app_for_ready = app.handle().clone();
            app.listen("desktop://frontend-ready", move |_| {
                let settings = app_for_ready
                    .state::<DesktopSettingsState>()
                    .settings
                    .lock()
                    .map(|guard| guard.clone())
                    .unwrap_or_default();
                emit_desktop_settings(&app_for_ready, &settings);
                refresh_tray_state(&app_for_ready);
            });

            refresh_tray_state(&app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_desktop_settings,
            update_desktop_settings,
            summon_main_window,
            hide_main_window,
            toggle_always_on_top,
            set_overlay_mode,
            set_close_to_tray_on_close
        ])
        .run(tauri::generate_context!())
        .expect("error while running SarahNode desktop shell");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn desktop_settings_defaults_missing_fields() {
        let parsed: DesktopSettings = serde_json::from_str("{}")
            .expect("missing settings fields should deserialize with defaults");
        assert!(parsed.always_on_top);
        assert!(parsed.overlay_mode);
        assert!(parsed.close_to_tray_on_close);
        assert!(parsed.voice_output_enabled);
        assert_eq!(parsed.version, CURRENT_SETTINGS_VERSION);
    }

    #[test]
    fn normalize_settings_migrates_version() {
        let migrated = normalize_settings(DesktopSettings {
            version: 0,
            ..DesktopSettings::default()
        });

        assert_eq!(migrated.version, CURRENT_SETTINGS_VERSION);
    }
}
