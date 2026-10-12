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
  aria2c_rpc_port: number;
  aria2c_secret: string;
  qbittorrent_host: string;
  qbittorrent_username: string;
  qbittorrent_password?: string;
  cookie_max_age: number;
  cookie_manual_path: string | null;
  cookie_browser_order: string[];
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

