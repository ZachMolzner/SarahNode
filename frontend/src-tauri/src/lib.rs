use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, RunEvent};

struct BackendProcessState {
    child: Mutex<Option<Child>>,
}

fn resolve_backend_data_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path()
        .app_data_dir()
        .ok()
        .map(|dir| dir.join("backend"))
}

fn try_spawn_backend_sidecar(app: &AppHandle) -> Result<Option<Child>, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let backend_dir = manifest_dir
        .parent()
        .and_then(|path| path.parent())
        .map(|path| path.join("backend"))
        .ok_or_else(|| "failed to resolve backend directory".to_string())?;

    let local_data_dir = resolve_backend_data_dir(app)
        .ok_or_else(|| "failed to resolve application data directory".to_string())?;
    let _ = fs::create_dir_all(&local_data_dir);

    let mut command = if cfg!(debug_assertions) {
        let mut cmd = Command::new("python");
        cmd.arg("run_server.py").current_dir(&backend_dir);
        cmd
    } else {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|err| format!("failed to resolve resource directory: {err}"))?;
        let exe = resource_dir.join("sidecar").join("sarahnode-backend.exe");
        let mut cmd = Command::new(exe);
        cmd.current_dir(resource_dir);
        cmd
    };

    command
        .env("LOCAL_DATA_DIR", &local_data_dir)
        .env("WEB_SEARCH_PROVIDER", "none")
        .env("BACKEND_BIND_ALL_INTERFACES", "0")
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    command
        .spawn()
        .map(Some)
        .map_err(|err| format!("failed to spawn backend sidecar: {err}"))
}

fn stop_backend_sidecar(app: &AppHandle) {
    if let Ok(mut guard) = app.state::<BackendProcessState>().child.lock() {
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
        }
        let _ = guard.take();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(BackendProcessState {
                child: Mutex::new(None),
            });

            if let Ok(Some(child)) = try_spawn_backend_sidecar(&app.handle()) {
                if let Ok(mut guard) = app.state::<BackendProcessState>().child.lock() {
                    *guard = Some(child);
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building SarahNode desktop shell");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit) {
            stop_backend_sidecar(app_handle);
        }
    });
}
