use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadItem {
    pub id: i64,
    pub url: String,
    pub title: String,
    pub status: String,
    pub download_type: String,
    pub download_speed: Option<String>,
    pub eta: Option<String>,
    #[serde(default)]
    pub progress: f64,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DownloadStats {
    pub total: i64,
    pub pending: i64,
    pub downloading: i64,
    pub completed: i64,
    pub failed: i64,
    pub paused: i64,
    pub is_running: bool,
    pub is_paused: bool,
}
