# Sharky TUI (Rust)

Ultra-fast, native Terminal User Interface for the **Sharky Download Engine**.

## Architecture
- Built with **[Ratatui](https://github.com/ratatui-org/ratatui)** and **[Crossterm](https://github.com/crossterm-rs/crossterm)**.
- Communicates asynchronously via Tokio and Reqwest with the Sharky Backend service on `http://localhost:8000`.

## Quickstart

### Prerequisites
- Rust & Cargo (1.75+)

### Running
Ensure the Sharky Backend is running:
```bash
python run.py server
```

Then in another terminal:
```bash
cd TUI
cargo run
```

Or configure custom backend address:
```bash
SHARKY_API_URL="http://192.168.1.100:8000" cargo run
```

### Controls
| Key | Action |
| --- | --- |
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `s` | Start pending downloads |
| `p` | Pause all active downloads |
| `r` | Resume all paused downloads |
| `x` | Stop all downloads |
| `q` / `Esc` | Exit TUI |
