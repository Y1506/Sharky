export interface DownloadItem {
  id: number;
  url: string;
  title: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'paused';
  download_type: 'video' | 'file' | 'torrent' | 'unknown';
  download_speed: string | null;
  eta: string | null;
  progress: number;
  error_message?: string | null;
  quality?: string;
  expected_hash?: string | null;
  actual_hash?: string | null;
  hash_algorithm?: string | null;
}

export interface DownloadStats {
  total: number;
  pending: number;
  downloading: number;
  completed: number;
  failed: number;
  paused: number;
  is_running: boolean;
  is_paused: boolean;
}

export interface AddDownloadPayload {
  url: string;
  quality?: string;
  include_subtitles?: boolean;
  embed_chapters?: boolean;
  expected_hash?: string;
  hash_algorithm?: string;
}

export interface BatchAddDownloadPayload {
  urls: string[];
  quality?: string;
  include_subtitles?: boolean;
  embed_chapters?: boolean;
}

export interface AppSettings {
  download_dir: string;
  concurrent_downloads: number;
  download_speed_limit: number;
  upload_speed_limit: number;
  max_connections_per_server: number;
  continue_download: boolean;
  auto_resume_unfinished: boolean;
  bt_save_magnet_as_torrent: boolean;
  bt_auto_download_content: boolean;
  bt_force_encryption: boolean;
  bt_keep_seeding: boolean;
  bt_seed_ratio: number;
  bt_seed_time: number;
  bt_listen_port: number;
  dht_listen_port: number;
  enable_upnp: boolean;
  proxy_enabled: boolean;
  proxy_url: string;
  bt_trackers: string;
  bt_tracker_sources: string[];
  bt_auto_update_trackers: boolean;
  bt_trackers_last_updated: string;
  user_agent: string;
  aria2_conf_path: string;
  session_path: string;
  log_path: string;
  log_level: string;
  aria2c_rpc_port: number;
  aria2c_secret: string;
  qbittorrent_host: string;
  qbittorrent_username: string;
  qbittorrent_password?: string;
  cookie_max_age: number;
  cookie_manual_path: string | null;
  cookie_browser_order: string[];
}

export interface WebLocalSettings {
  theme: 'auto' | 'light' | 'dark';
  hideAppMenu: boolean;
  autoHideWindow: boolean;
  showDownloadProgressBar: boolean;
  language: string;
  rememberWindowLayout: boolean;
  autoSaveToDevice: boolean;
  soundNotification: boolean;
  desktopNotification: boolean;
}

export interface CookieStatus {
  has_cached_cookies: boolean;
  cached_cookie_age: string | null;
  cached_cookie_fresh: boolean;
  manual_path: string | null;
  browser_order: string[];
  zen_available: boolean;
  brave_available: boolean;
}

