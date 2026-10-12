mod app;
mod client;
mod models;
mod ui;

use std::{io, time::Duration};
use crossterm::{
    event::{self, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};

use app::App;
use client::ApiClient;
use ui::render_ui;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let backend_url = std::env::var("SHARKY_API_URL").unwrap_or_else(|_| "http://localhost:8000".to_string());
    let mut app = App::new(backend_url.clone());
    let client = ApiClient::new(backend_url);

    // Setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut last_poll = std::time::Instant::now();
    let poll_interval = Duration::from_millis(1000);

    loop {
        // Poll backend
        if last_poll.elapsed() >= poll_interval {
            if let Ok(downloads) = client.fetch_downloads().await {
                app.downloads = downloads;
                app.is_connected = true;
                app.status_message = "Connected to Sharky Engine".into();
            } else {
                app.is_connected = false;
                app.status_message = "Backend unavailable".into();
            }

            if let Ok(stats) = client.fetch_stats().await {
                app.stats = stats;
            }

            last_poll = std::time::Instant::now();
        }

        // Draw UI
        terminal.draw(|f| render_ui(f, &app))?;

        // Handle user keyboard events with timeout
        if event::poll(Duration::from_millis(100))? {
            if let Event::Key(key) = event::read()? {
                match key.code {
                    KeyCode::Char('q') | KeyCode::Esc => break,
                    KeyCode::Down | KeyCode::Char('j') => app.next_item(),
                    KeyCode::Up | KeyCode::Char('k') => app.previous_item(),
                    KeyCode::Char('s') => {
                        let _ = client.start_downloads().await;
                    }
                    KeyCode::Char('p') => {
                        let _ = client.pause_downloads().await;
                    }
                    KeyCode::Char('r') => {
                        let _ = client.resume_downloads().await;
                    }
                    KeyCode::Char('x') => {
                        let _ = client.stop_downloads().await;
                    }
                    _ => {}
                }
            }
        }
    }

    // Teardown terminal
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    Ok(())
}
