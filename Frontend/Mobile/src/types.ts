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
