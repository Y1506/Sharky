use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table},
    Frame,
};

use crate::app::App;

pub fn render_ui(frame: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Header
            Constraint::Length(3), // Stats
            Constraint::Min(6),    // Main Table
            Constraint::Length(3), // Footer / Keybinds
        ])
        .split(frame.area());

    render_header(frame, chunks[0], app);
    render_stats(frame, chunks[1], app);
    render_table(frame, chunks[2], app);
    render_footer(frame, chunks[3]);
}

fn render_header(frame: &mut Frame, area: Rect, app: &App) {
    let status_color = if app.is_connected {
        Color::Green
    } else {
        Color::Red
    };
    let status_text = if app.is_connected {
        "● CONNECTED"
    } else {
        "○ OFFLINE"
    };

    let title_line = Line::from(vec![
        Span::styled(
            " SHARKY ",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("— High Performance Download Engine [TUI] "),
        Span::styled(status_text, Style::default().fg(status_color)),
    ]);

    let header_block = Block::default()
        .borders(Borders::ALL)
        .style(Style::default().fg(Color::DarkGray));
    let paragraph = Paragraph::new(title_line).block(header_block);
    frame.render_widget(paragraph, area);
}

fn render_stats(frame: &mut Frame, area: Rect, app: &App) {
    let stats_text = Line::from(vec![
        Span::styled(" Active: ", Style::default().fg(Color::Gray)),
        Span::styled(
            format!("{} ", app.stats.downloading),
            Style::default().fg(Color::LightBlue),
        ),
        Span::styled(" Pending: ", Style::default().fg(Color::Gray)),
        Span::styled(
            format!("{} ", app.stats.pending),
            Style::default().fg(Color::Yellow),
        ),
        Span::styled(" Done: ", Style::default().fg(Color::Gray)),
        Span::styled(
            format!("{} ", app.stats.completed),
            Style::default().fg(Color::Green),
        ),
        Span::styled(" Failed: ", Style::default().fg(Color::Gray)),
        Span::styled(
            format!("{} ", app.stats.failed),
            Style::default().fg(Color::Red),
        ),
        Span::styled(
            format!("| Status: {}", app.status_message),
            Style::default().fg(Color::DarkGray),
        ),
    ]);

    let stats_block = Block::default()
        .borders(Borders::ALL)
        .style(Style::default().fg(Color::DarkGray));
    let paragraph = Paragraph::new(stats_text).block(stats_block);
    frame.render_widget(paragraph, area);
}

fn render_table(frame: &mut Frame, area: Rect, app: &App) {
    let rows: Vec<Row> = app
        .downloads
        .iter()
        .enumerate()
        .map(|(idx, item)| {
            let is_selected = idx == app.selected_index;
            let status_style = match item.status.as_str() {
                "downloading" => Style::default().fg(Color::Cyan),
                "completed" => Style::default().fg(Color::Green),
                "failed" => Style::default().fg(Color::Red),
                "paused" => Style::default().fg(Color::Yellow),
                _ => Style::default().fg(Color::Gray),
            };

            let row_style = if is_selected {
                Style::default().bg(Color::Rgb(20, 30, 50))
            } else {
                Style::default()
            };

            Row::new(vec![
                Cell::from(format!("{}", item.id)),
                Cell::from(item.download_type.clone()),
                Cell::from(item.title.clone()),
                Cell::from(item.status.clone()).style(status_style),
                Cell::from(format!("{:.1}%", item.progress)),
                Cell::from(item.download_speed.clone().unwrap_or_else(|| "-".into())),
                Cell::from(item.eta.clone().unwrap_or_else(|| "-".into())),
            ])
            .style(row_style)
        })
        .collect();

    let widths = [
        Constraint::Length(5),  // ID
        Constraint::Length(10), // Type
        Constraint::Min(25),    // Title
        Constraint::Length(14), // Status
        Constraint::Length(10), // Progress
        Constraint::Length(12), // Speed
        Constraint::Length(10), // ETA
    ];

    let table = Table::new(rows, widths)
        .header(
            Row::new(vec!["ID", "Type", "Title", "Status", "Progress", "Speed", "ETA"])
                .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        )
        .block(
            Block::default()
                .title(" Downloads Queue ")
                .borders(Borders::ALL)
                .style(Style::default().fg(Color::DarkGray)),
        );

    frame.render_widget(table, area);
}

fn render_footer(frame: &mut Frame, area: Rect) {
    let help_line = Line::from(vec![
        Span::styled(" [s] ", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
        Span::raw("Start  "),
        Span::styled(" [p] ", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
        Span::raw("Pause  "),
        Span::styled(" [r] ", Style::default().fg(Color::Blue).add_modifier(Modifier::BOLD)),
        Span::raw("Resume  "),
        Span::styled(" [x] ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
        Span::raw("Stop  "),
        Span::styled(" [↑/↓] ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw("Navigate  "),
        Span::styled(" [q] ", Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)),
        Span::raw("Quit"),
    ]);

    let footer_block = Block::default()
        .borders(Borders::ALL)
        .style(Style::default().fg(Color::DarkGray));
    let paragraph = Paragraph::new(help_line).block(footer_block);
    frame.render_widget(paragraph, area);
}
