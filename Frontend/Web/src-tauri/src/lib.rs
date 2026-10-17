use tauri_plugin_shell::ShellExt;

#[tauri::command]
fn get_backend_url() -> String {
    "http://localhost:8000".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .setup(|app| {
            // Spawn the Python backend sidecar if available
            let shell = app.shell();
            if let Ok(sidecar) = shell.sidecar("sharky-backend") {
                if let Ok((_rx, _child)) = sidecar.args(&["server"]).spawn() {
                    eprintln!("Sharky backend sidecar spawned successfully");
                } else {
                    eprintln!("Warning: Failed to spawn sidecar process (may already be running or running in dev)");
                }
            } else {
                eprintln!("Warning: sharky-backend sidecar not found (running in dev mode without bundled backend)");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Sharky");
}

#[cfg(feature = "tui")]
pub fn run_tui() {
    eprintln!("Sharky TUI mode started");
}
