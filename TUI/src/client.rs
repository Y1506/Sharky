use anyhow::Result;
use reqwest::Client;

use crate::models::{DownloadItem, DownloadStats};

pub struct ApiClient {
    client: Client,
    base_url: String,
}

impl ApiClient {
    pub fn new(base_url: String) -> Self {
        Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(3))
                .build()
                .unwrap_or_default(),
            base_url,
        }
    }

    pub async fn fetch_downloads(&self) -> Result<Vec<DownloadItem>> {
        let url = format!("{}/api/downloads", self.base_url);
        let items = self.client.get(&url).send().await?.json().await?;
        Ok(items)
    }

    pub async fn fetch_stats(&self) -> Result<DownloadStats> {
        let url = format!("{}/api/stats", self.base_url);
        let stats = self.client.get(&url).send().await?.json().await?;
        Ok(stats)
    }

    pub async fn start_downloads(&self) -> Result<()> {
        let url = format!("{}/api/downloads/start", self.base_url);
        self.client.post(&url).send().await?;
        Ok(())
    }

    pub async fn pause_downloads(&self) -> Result<()> {
        let url = format!("{}/api/downloads/pause", self.base_url);
        self.client.post(&url).send().await?;
        Ok(())
    }

    pub async fn resume_downloads(&self) -> Result<()> {
        let url = format!("{}/api/downloads/resume", self.base_url);
        self.client.post(&url).send().await?;
        Ok(())
    }

    pub async fn stop_downloads(&self) -> Result<()> {
        let url = format!("{}/api/downloads/stop", self.base_url);
        self.client.post(&url).send().await?;
        Ok(())
    }
}
