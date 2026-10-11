use crate::models::{DownloadItem, DownloadStats};

pub struct App {
    pub downloads: Vec<DownloadItem>,
    pub stats: DownloadStats,
    pub selected_index: usize,
    pub is_connected: bool,
    pub server_url: String,
    pub status_message: String,
}

impl App {
    pub fn new(server_url: String) -> Self {
        Self {
            downloads: Vec::new(),
            stats: DownloadStats::default(),
            selected_index: 0,
            is_connected: false,
            server_url,
            status_message: String::from("Connecting to Sharky backend..."),
        }
    }

    pub fn next_item(&mut self) {
        if !self.downloads.is_empty() {
            self.selected_index = (self.selected_index + 1) % self.downloads.len();
        }
    }

    pub fn previous_item(&mut self) {
        if !self.downloads.is_empty() {
            if self.selected_index == 0 {
                self.selected_index = self.downloads.len() - 1;
            } else {
                self.selected_index -= 1;
            }
        }
    }
}
