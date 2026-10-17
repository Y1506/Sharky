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

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AppSettings {
    pub download_dir: Option<String>,
    pub concurrent_downloads: Option<i64>,
    pub download_speed_limit: Option<i64>,
    pub upload_speed_limit: Option<i64>,
    pub max_connections_per_server: Option<i64>,
    pub continue_download: Option<bool>,
    pub auto_resume_unfinished: Option<bool>,
    pub proxy_enabled: Option<bool>,
    pub proxy_url: Option<String>,
    pub user_agent: Option<String>,
}
