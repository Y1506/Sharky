// Prevents additional console window on Windows in release (GUI mode only)
#![cfg_attr(
    all(not(debug_assertions), not(feature = "tui")),
    windows_subsystem = "windows"
)]

use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    let is_tui = args.iter().any(|a| a == "--tui" || a == "-t");

    if is_tui {
        #[cfg(feature = "tui")]
        {
            eprintln!("Starting Sharky TUI mode...");
            sharky_desktop_lib::run_tui();
        }
        #[cfg(not(feature = "tui"))]
        {
            eprintln!("TUI mode not enabled in this build. Rebuild with --features tui");
            std::process::exit(1);
        }
    } else {
        sharky_desktop_lib::run();
    }
}
