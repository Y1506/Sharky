import { useEffect, useState } from 'react';
import type { DownloadItem, DownloadStats, AddDownloadPayload, BatchAddDownloadPayload, AppSettings, CookieStatus } from './types';

const API_BASE = '/api';

export async function fetchDownloads(): Promise<DownloadItem[]> {
  const res = await fetch(`${API_BASE}/downloads`);
  if (!res.ok) throw new Error('Failed to fetch downloads');
  return res.json();
}

export async function fetchStats(): Promise<DownloadStats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function addDownload(payload: AddDownloadPayload): Promise<{ id: number; message: string }> {
  const res = await fetch(`${API_BASE}/downloads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to add download' }));
    throw new Error(error.detail || 'Failed to add download');
  }
  return res.json();
}

export async function addBatchDownloads(payload: BatchAddDownloadPayload): Promise<{ added: number; skipped: number; failed: number }> {
  const res = await fetch(`${API_BASE}/downloads/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to import batch downloads');
  return res.json();
}

export async function startDownloads(): Promise<{ started: boolean }> {
  const res = await fetch(`${API_BASE}/downloads/start`, { method: 'POST' });
  return res.json();
}

export async function pauseDownloads(): Promise<void> {
  await fetch(`${API_BASE}/downloads/pause`, { method: 'POST' });
}

export async function resumeDownloads(): Promise<void> {
  await fetch(`${API_BASE}/downloads/resume`, { method: 'POST' });
}

export async function stopDownloads(): Promise<void> {
  await fetch(`${API_BASE}/downloads/stop`, { method: 'POST' });
}

export async function retryFailedDownloads(): Promise<void> {
  await fetch(`${API_BASE}/downloads/retry-failed`, { method: 'POST' });
}

export async function clearCompletedDownloads(): Promise<void> {
  await fetch(`${API_BASE}/downloads/completed`, { method: 'DELETE' });
}

export async function removeDownload(id: number): Promise<void> {
  await fetch(`${API_BASE}/downloads/${id}`, { method: 'DELETE' });
}

export async function fetchSettings(): Promise<AppSettings> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateSettings(payload: Partial<AppSettings>): Promise<{ message: string; settings: AppSettings }> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to update settings' }));
    throw new Error(error.detail || 'Failed to update settings');
  }
  return res.json();
}

export async function fetchCookieStatus(): Promise<CookieStatus> {
  const res = await fetch(`${API_BASE}/settings/cookies/status`);
  if (!res.ok) throw new Error('Failed to fetch cookie status');
  return res.json();
}

export async function clearCookies(): Promise<void> {
  const res = await fetch(`${API_BASE}/settings/cookies/clear`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear cookies');
}

export async function updateTrackers(): Promise<{ message: string; trackers_count: number; settings: AppSettings }> {
  const res = await fetch(`${API_BASE}/settings/trackers/update`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to update trackers list');
  return res.json();
}

export async function resetSession(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/settings/session/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset download session');
  return res.json();
}

export async function factoryReset(): Promise<{ message: string; settings: AppSettings }> {
  const res = await fetch(`${API_BASE}/settings/factory-reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to factory reset settings');
  return res.json();
}

export function useSharkyWebSocket() {
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [stats, setStats] = useState<DownloadStats | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/progress`;
    let ws: WebSocket | null = null;
    let timer: any = null;

    function connect() {
      try {
        ws = new WebSocket(wsUrl);
        ws.onopen = () => setConnected(true);
        ws.onclose = () => {
          setConnected(false);
          timer = setTimeout(connect, 2000);
        };
        ws.onerror = () => ws?.close();
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.downloads) setDownloads(data.downloads);
            if (data.stats) setStats(data.stats);
          } catch {
            // Ignore parse errors
          }
        };
      } catch {
        timer = setTimeout(connect, 3000);
      }
    }

    connect();

    return () => {
      clearTimeout(timer);
      if (ws) ws.close();
    };
  }, []);

  return { downloads, stats, connected };
}
