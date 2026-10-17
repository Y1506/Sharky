import React, { useState, useEffect } from 'react';
import {
  X, Save, RefreshCw, Check, AlertCircle,
  Cookie, Folder, Sliders, Wrench, FlaskConical,
  Copy, Moon, Sun, Monitor, RotateCcw, Trash2
} from 'lucide-react';
import {
  fetchSettings, updateSettings, fetchCookieStatus, clearCookies,
  updateTrackers, resetSession, factoryReset
} from '../api';
import type { AppSettings, WebLocalSettings, CookieStatus } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  localSettings: WebLocalSettings;
  onUpdateLocalSettings: (settings: WebLocalSettings) => void;
}

const DEFAULT_CENTRAL_SETTINGS: AppSettings = {
  download_dir: '/downloads',
  concurrent_downloads: 5,
  download_speed_limit: 0,
  upload_speed_limit: 0,
  max_connections_per_server: 16,
  continue_download: true,
  auto_resume_unfinished: false,
  bt_save_magnet_as_torrent: true,
  bt_auto_download_content: true,
  bt_force_encryption: false,
  bt_keep_seeding: false,
  bt_seed_ratio: 1.0,
  bt_seed_time: 60,
  bt_listen_port: 21301,
  dht_listen_port: 26701,
  enable_upnp: true,
  proxy_enabled: false,
  proxy_url: '',
  bt_trackers: '',
  bt_tracker_sources: [
    'https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best_ip.txt',
    'https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/best.txt'
  ],
  bt_auto_update_trackers: true,
  bt_trackers_last_updated: '',
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  aria2_conf_path: '',
  session_path: '',
  log_path: '',
  log_level: 'warn',
  aria2c_rpc_port: 6800,
  aria2c_secret: 'aria2secret',
  qbittorrent_host: 'http://localhost:8080',
  qbittorrent_username: 'admin',
  qbittorrent_password: '',
  cookie_max_age: 86400,
  cookie_manual_path: null,
  cookie_browser_order: ['zen', 'brave'],
};

export default function SettingsModal({
  isOpen,
  onClose,
  localSettings,
  onUpdateLocalSettings,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'basic' | 'advanced' | 'lab' | 'cookies'>('basic');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Centralized settings state
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_CENTRAL_SETTINGS);
  const [cookieStatus, setCookieStatus] = useState<CookieStatus | null>(null);

  // Local settings draft state
  const [localDraft, setLocalDraft] = useState<WebLocalSettings>(localSettings);

  // Unit helpers for speed limits (KB/s vs MB/s)
  const [dlUnit, setDlUnit] = useState<'KB/s' | 'MB/s'>('KB/s');
  const [ulUnit, setUlUnit] = useState<'KB/s' | 'MB/s'>('KB/s');
  const [dlValue, setDlValue] = useState<number>(0);
  const [ulValue, setUlValue] = useState<number>(0);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setLocalDraft(localSettings);
    }
  }, [isOpen]);

  const loadData = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [sData, cData] = await Promise.all([
        fetchSettings(),
        fetchCookieStatus(),
      ]);
      setSettings(sData);
      setCookieStatus(cData);

      // Initialize speed limit display units
      if (sData.download_speed_limit >= 1048576 && sData.download_speed_limit % 1048576 === 0) {
        setDlUnit('MB/s');
        setDlValue(sData.download_speed_limit / 1048576);
      } else {
        setDlUnit('KB/s');
        setDlValue(Math.round(sData.download_speed_limit / 1024));
      }

      if (sData.upload_speed_limit >= 1048576 && sData.upload_speed_limit % 1048576 === 0) {
        setUlUnit('MB/s');
        setUlValue(sData.upload_speed_limit / 1048576);
      } else {
        setUlUnit('KB/s');
        setUlValue(Math.round(sData.upload_speed_limit / 1024));
      }
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to load settings', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, fieldId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleDlSpeedChange = (val: number, unit: 'KB/s' | 'MB/s') => {
    setDlValue(val);
    setDlUnit(unit);
    const bytes = unit === 'MB/s' ? val * 1048576 : val * 1024;
    setSettings(prev => ({ ...prev, download_speed_limit: bytes }));
  };

  const handleUlSpeedChange = (val: number, unit: 'KB/s' | 'MB/s') => {
    setUlValue(val);
    setUlUnit(unit);
    const bytes = unit === 'MB/s' ? val * 1048576 : val * 1024;
    setSettings(prev => ({ ...prev, upload_speed_limit: bytes }));
  };

  const handleSaveAndApply = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      // 1. Save Centralized Settings to Backend
      const res = await updateSettings(settings);
      setSettings(res.settings);

      // 2. Save Decentralized (Local) Settings to Web UI
      onUpdateLocalSettings(localDraft);

      setMessage({ text: 'Settings saved & applied successfully across engine and client!', type: 'success' });
      setTimeout(() => {
        setMessage(null);
      }, 3500);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to save settings', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateTrackers = async () => {
    setActionLoading('trackers');
    try {
      const res = await updateTrackers();
      setSettings(res.settings);
      setMessage({ text: res.message, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to update trackers', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleResetSession = async () => {
    if (!window.confirm('Are you sure you want to reset the download session file?')) return;
    setActionLoading('session');
    try {
      const res = await resetSession();
      setMessage({ text: res.message, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to reset session', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleFactoryReset = async () => {
    if (!window.confirm('Reset ALL centralized settings back to factory default values?')) return;
    setActionLoading('factory');
    try {
      const res = await factoryReset();
      setSettings(res.settings);
      setMessage({ text: res.message, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to factory reset', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearCookies = async () => {
    setActionLoading('cookies');
    try {
      await clearCookies();
      const updatedStatus = await fetchCookieStatus();
      setCookieStatus(updatedStatus);
      setMessage({ text: 'Cached cookies cleared successfully', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to clear cookies', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleProtocolRegister = (proto: string) => {
    try {
      if (typeof window !== 'undefined' && 'registerProtocolHandler' in navigator) {
        const handlerUrl = `${window.location.origin}/#add?url=%s`;
        navigator.registerProtocolHandler(proto, handlerUrl);
        setMessage({ text: `Registered browser handler for ${proto}://`, type: 'success' });
      } else {
        alert('Protocol handler registration not supported in this browser environment.');
      }
    } catch (e: any) {
      alert(`Registration note: ${e.message}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 60,
      backdropFilter: 'blur(6px)',
      padding: '16px',
    }}>
      <div style={{
        backgroundColor: '#18181b',
        border: '1px solid #27272a',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '920px',
        height: '88vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        overflow: 'hidden',
        color: '#f4f4f5',
        fontFamily: 'system-ui, sans-serif'
      }}>
        {/* Header Bar */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid #27272a',
          backgroundColor: '#202024',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Sliders style={{ width: '16px', height: '16px', color: '#ffffff' }} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>Preferences</h2>
              <span style={{ fontSize: '11px', color: '#a1a1aa' }}>Centralized Engine & Decentralized Client Configuration</span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#a1a1aa',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X style={{ width: '18px', height: '18px' }} />
          </button>
        </div>

        {/* Message Banner */}
        {message && (
          <div style={{
            padding: '10px 20px',
            backgroundColor: message.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            borderBottom: `1px solid ${message.type === 'success' ? '#10b981' : '#ef4444'}`,
            color: message.type === 'success' ? '#34d399' : '#f87171',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px',
          }}>
            {message.type === 'success' ? <Check style={{ width: '16px', height: '16px' }} /> : <AlertCircle style={{ width: '16px', height: '16px' }} />}
            <span>{message.text}</span>
          </div>
        )}

        {/* Modal Layout: Sidebar + Form Body */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Motrix-Style Left Sidebar */}
          <div style={{
            width: '180px',
            backgroundColor: '#141416',
            borderRight: '1px solid #27272a',
            padding: '16px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}>
            <button
              type="button"
              onClick={() => setActiveTab('basic')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'basic' ? '#27272a' : 'transparent',
                color: activeTab === 'basic' ? '#38bdf8' : '#a1a1aa',
                fontWeight: activeTab === 'basic' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <Sliders style={{ width: '16px', height: '16px' }} />
              <span>Basic</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('advanced')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'advanced' ? '#27272a' : 'transparent',
                color: activeTab === 'advanced' ? '#38bdf8' : '#a1a1aa',
                fontWeight: activeTab === 'advanced' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <Wrench style={{ width: '16px', height: '16px' }} />
              <span>Advanced</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('lab')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'lab' ? '#27272a' : 'transparent',
                color: activeTab === 'lab' ? '#38bdf8' : '#a1a1aa',
                fontWeight: activeTab === 'lab' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <FlaskConical style={{ width: '16px', height: '16px' }} />
              <span>Lab</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('cookies')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'cookies' ? '#27272a' : 'transparent',
                color: activeTab === 'cookies' ? '#38bdf8' : '#a1a1aa',
                fontWeight: activeTab === 'cookies' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <Cookie style={{ width: '16px', height: '16px' }} />
              <span>Cookies & Auth</span>
            </button>
          </div>

          {/* Form Content Area */}
          <form onSubmit={handleSaveAndApply} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {loading ? (
                <div style={{ textAlign: 'center', padding: '60px', color: '#a1a1aa' }}>
                  <RefreshCw style={{ width: '28px', height: '28px', animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
                  <div>Loading engine configuration...</div>
                </div>
              ) : (
                <>
                  {/* TAB 1: BASIC PREFERENCES */}
                  {activeTab === 'basic' && (
                    <>
                      {/* Appearance (Decentralized Local Setting) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Appearance:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#581c87', color: '#d8b4fe' }}>Local Browser</span>
                        </div>
                        <div style={{ display: 'flex', gap: '16px', marginBottom: '12px' }}>
                          {(['auto', 'light', 'dark'] as const).map((t) => (
                            <label
                              key={t}
                              style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: '6px',
                                cursor: 'pointer',
                              }}
                            >
                              <div style={{
                                width: '70px',
                                height: '42px',
                                borderRadius: '6px',
                                border: localDraft.theme === t ? '2px solid #38bdf8' : '1px solid #3f3f46',
                                backgroundColor: t === 'light' ? '#f4f4f5' : t === 'dark' ? '#09090b' : '#27272a',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: t === 'light' ? '#09090b' : '#f4f4f5',
                              }}>
                                {t === 'auto' ? <Monitor style={{ width: '16px', height: '16px' }} /> : t === 'light' ? <Sun style={{ width: '16px', height: '16px' }} /> : <Moon style={{ width: '16px', height: '16px' }} />}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <input
                                  type="radio"
                                  name="theme"
                                  checked={localDraft.theme === t}
                                  onChange={() => setLocalDraft({ ...localDraft, theme: t })}
                                  style={{ accentColor: '#38bdf8', cursor: 'pointer' }}
                                />
                                <span style={{ fontSize: '12px', textTransform: 'capitalize', color: '#d4d4d8' }}>{t}</span>
                              </div>
                            </label>
                          ))}
                        </div>

                        {/* Local display toggles */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', color: '#d4d4d8' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={localDraft.hideAppMenu}
                              onChange={(e) => setLocalDraft({ ...localDraft, hideAppMenu: e.target.checked })}
                              style={{ accentColor: '#38bdf8' }}
                            />
                            Hide App Menu (Windows & Linux Only)
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={localDraft.autoHideWindow}
                              onChange={(e) => setLocalDraft({ ...localDraft, autoHideWindow: e.target.checked })}
                              style={{ accentColor: '#38bdf8' }}
                            />
                            Auto Hide Window
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={localDraft.showDownloadProgressBar}
                              onChange={(e) => setLocalDraft({ ...localDraft, showDownloadProgressBar: e.target.checked })}
                              style={{ accentColor: '#38bdf8' }}
                            />
                            Show download progress bar
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={localDraft.autoSaveToDevice}
                              onChange={(e) => setLocalDraft({ ...localDraft, autoSaveToDevice: e.target.checked })}
                              style={{ accentColor: '#38bdf8' }}
                            />
                            Auto-Save to Device / Browser (automatically download to browser Downloads folder on finish)
                          </label>
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Language (Local) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Language:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#581c87', color: '#d8b4fe' }}>Local Browser</span>
                        </div>
                        <select
                          value={localDraft.language}
                          onChange={(e) => setLocalDraft({ ...localDraft, language: e.target.value })}
                          style={{
                            padding: '8px 12px',
                            backgroundColor: '#27272a',
                            border: '1px solid #3f3f46',
                            borderRadius: '6px',
                            color: '#ffffff',
                            fontSize: '13px',
                            width: '240px',
                          }}
                        >
                          <option value="en">English</option>
                          <option value="zh">简体中文 (Chinese)</option>
                          <option value="es">Español (Spanish)</option>
                          <option value="de">Deutsch (German)</option>
                          <option value="ja">日本語 (Japanese)</option>
                        </select>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Startup (Hybrid Local + Centralized) */}
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5', marginBottom: '8px' }}>Startup:</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', color: '#d4d4d8' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={localDraft.rememberWindowLayout}
                              onChange={(e) => setLocalDraft({ ...localDraft, rememberWindowLayout: e.target.checked })}
                              style={{ accentColor: '#38bdf8' }}
                            />
                            Keep size and position of the window when exited
                            <span style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#581c87', color: '#d8b4fe' }}>Local</span>
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={settings.auto_resume_unfinished}
                              onChange={(e) => setSettings({ ...settings, auto_resume_unfinished: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            Automatically resume all unfinished tasks
                            <span style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                          </label>
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Default Path (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Default Path:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <input
                            type="text"
                            value={settings.download_dir}
                            onChange={(e) => setSettings({ ...settings, download_dir: e.target.value })}
                            placeholder="/downloads"
                            style={{
                              flex: 1,
                              padding: '8px 12px',
                              backgroundColor: '#27272a',
                              border: '1px solid #3f3f46',
                              borderRadius: '6px',
                              color: '#ffffff',
                              fontSize: '13px',
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => alert(`Server storage directory: ${settings.download_dir}`)}
                            style={{
                              padding: '8px 12px',
                              backgroundColor: '#27272a',
                              border: '1px solid #3f3f46',
                              borderRadius: '6px',
                              color: '#a1a1aa',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                            }}
                            title="Browse directory"
                          >
                            <Folder style={{ width: '16px', height: '16px' }} />
                          </button>
                        </div>
                        <span style={{ fontSize: '11px', color: '#71717a', marginTop: '4px', display: 'block' }}>
                          Server base directory for files, videos, audio, and torrents.
                        </span>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Transmission Limits (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Transmission:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Upload limit (0 = Unlimited):</label>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <input
                                type="number"
                                min="0"
                                value={ulValue}
                                onChange={(e) => handleUlSpeedChange(Math.max(0, parseInt(e.target.value) || 0), ulUnit)}
                                style={{
                                  flex: 1,
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                }}
                              />
                              <select
                                value={ulUnit}
                                onChange={(e) => handleUlSpeedChange(ulValue, e.target.value as any)}
                                style={{
                                  padding: '8px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '12px',
                                }}
                              >
                                <option value="KB/s">KB/s</option>
                                <option value="MB/s">MB/s</option>
                              </select>
                            </div>
                          </div>

                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Download limit (0 = Unlimited):</label>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <input
                                type="number"
                                min="0"
                                value={dlValue}
                                onChange={(e) => handleDlSpeedChange(Math.max(0, parseInt(e.target.value) || 0), dlUnit)}
                                style={{
                                  flex: 1,
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                }}
                              />
                              <select
                                value={dlUnit}
                                onChange={(e) => handleDlSpeedChange(dlValue, e.target.value as any)}
                                style={{
                                  padding: '8px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '12px',
                                }}
                              >
                                <option value="KB/s">KB/s</option>
                                <option value="MB/s">MB/s</option>
                              </select>
                            </div>
                          </div>
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* BitTorrent (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>BitTorrent:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', color: '#d4d4d8' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={settings.bt_save_magnet_as_torrent}
                              onChange={(e) => setSettings({ ...settings, bt_save_magnet_as_torrent: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            Save magnet link as torrent file
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={settings.bt_auto_download_content}
                              onChange={(e) => setSettings({ ...settings, bt_auto_download_content: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            Automatically download magnet and torrent content
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={settings.bt_force_encryption}
                              onChange={(e) => setSettings({ ...settings, bt_force_encryption: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            BT force encryption
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={settings.bt_keep_seeding}
                              onChange={(e) => setSettings({ ...settings, bt_keep_seeding: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            Keep seeding until manually stopped
                          </label>

                          {!settings.bt_keep_seeding && (
                            <div style={{ display: 'flex', gap: '20px', marginTop: '4px' }}>
                              <div>
                                <label style={{ display: 'block', fontSize: '11px', color: '#a1a1aa' }}>Seed Ratio</label>
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0"
                                  value={settings.bt_seed_ratio}
                                  onChange={(e) => setSettings({ ...settings, bt_seed_ratio: parseFloat(e.target.value) || 0 })}
                                  style={{
                                    padding: '6px 8px',
                                    backgroundColor: '#27272a',
                                    border: '1px solid #3f3f46',
                                    borderRadius: '6px',
                                    color: '#ffffff',
                                    fontSize: '12px',
                                    width: '100px',
                                  }}
                                />
                              </div>

                              <div>
                                <label style={{ display: 'block', fontSize: '11px', color: '#a1a1aa' }}>Seed Time (minutes)</label>
                                <input
                                  type="number"
                                  min="0"
                                  value={settings.bt_seed_time}
                                  onChange={(e) => setSettings({ ...settings, bt_seed_time: parseInt(e.target.value) || 0 })}
                                  style={{
                                    padding: '6px 8px',
                                    backgroundColor: '#27272a',
                                    border: '1px solid #3f3f46',
                                    borderRadius: '6px',
                                    color: '#ffffff',
                                    fontSize: '12px',
                                    width: '120px',
                                  }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Task Management (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Task Management:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '8px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Maximum active tasks (1..64):</label>
                            <input
                              type="number"
                              min="1"
                              max="64"
                              value={settings.concurrent_downloads}
                              onChange={(e) => setSettings({ ...settings, concurrent_downloads: Math.min(64, Math.max(1, parseInt(e.target.value) || 1)) })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                              }}
                            />
                          </div>

                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Max connections per server:</label>
                            <input
                              type="number"
                              min="1"
                              max="64"
                              value={settings.max_connections_per_server}
                              onChange={(e) => setSettings({ ...settings, max_connections_per_server: Math.min(64, Math.max(1, parseInt(e.target.value) || 1)) })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                              }}
                            />
                          </div>
                        </div>

                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: '#d4d4d8' }}>
                          <input
                            type="checkbox"
                            checked={settings.continue_download}
                            onChange={(e) => setSettings({ ...settings, continue_download: e.target.checked })}
                            style={{ accentColor: '#0284c7' }}
                          />
                          Continue (Enable resume capability for downloads)
                        </label>
                      </div>
                    </>
                  )}

                  {/* TAB 2: ADVANCED PREFERENCES */}
                  {activeTab === 'advanced' && (
                    <>
                      {/* Proxy (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Proxy:</span>
                            <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                          </div>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px' }}>
                            <input
                              type="checkbox"
                              checked={settings.proxy_enabled}
                              onChange={(e) => setSettings({ ...settings, proxy_enabled: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            <span>Enable Proxy</span>
                          </label>
                        </div>
                        {settings.proxy_enabled && (
                          <input
                            type="text"
                            value={settings.proxy_url}
                            onChange={(e) => setSettings({ ...settings, proxy_url: e.target.value })}
                            placeholder="e.g. http://127.0.0.1:7890 or socks5://127.0.0.1:1080"
                            style={{
                              width: '100%',
                              padding: '8px 12px',
                              backgroundColor: '#27272a',
                              border: '1px solid #3f3f46',
                              borderRadius: '6px',
                              color: '#ffffff',
                              fontSize: '13px',
                            }}
                          />
                        )}
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Tracker Servers (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Tracker Servers:</span>
                            <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                          </div>
                          <button
                            type="button"
                            onClick={handleUpdateTrackers}
                            disabled={actionLoading === 'trackers'}
                            style={{
                              padding: '4px 10px',
                              backgroundColor: '#0284c7',
                              color: 'white',
                              border: 'none',
                              borderRadius: '6px',
                              fontSize: '12px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <RefreshCw style={{ width: '13px', height: '13px', animation: actionLoading === 'trackers' ? 'spin 1s linear infinite' : 'none' }} />
                            <span>Update Trackers Now</span>
                          </button>
                        </div>

                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                          {settings.bt_tracker_sources.map((src, idx) => (
                            <span
                              key={idx}
                              style={{
                                fontSize: '11px',
                                padding: '3px 8px',
                                borderRadius: '4px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                color: '#38bdf8',
                              }}
                            >
                              {src.split('/').pop()}
                            </span>
                          ))}
                        </div>

                        <textarea
                          rows={6}
                          value={settings.bt_trackers}
                          onChange={(e) => setSettings({ ...settings, bt_trackers: e.target.value })}
                          placeholder="udp://tracker.opentrackr.org:1337/announce&#10;udp://open.tracker.cl:1337/announce"
                          style={{
                            width: '100%',
                            padding: '8px 10px',
                            backgroundColor: '#27272a',
                            border: '1px solid #3f3f46',
                            borderRadius: '6px',
                            color: '#e4e4e7',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            boxSizing: 'border-box',
                          }}
                        />

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '12px', color: '#71717a' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: '#a1a1aa' }}>
                            <input
                              type="checkbox"
                              checked={settings.bt_auto_update_trackers}
                              onChange={(e) => setSettings({ ...settings, bt_auto_update_trackers: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            Update tracker list every day automatically
                          </label>
                          {settings.bt_trackers_last_updated && (
                            <span>Last updated: {settings.bt_trackers_last_updated}</span>
                          )}
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* RPC Configuration (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>RPC Server:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>RPC Listen Port:</label>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <input
                                type="number"
                                min="1024"
                                max="65535"
                                value={settings.aria2c_rpc_port}
                                onChange={(e) => setSettings({ ...settings, aria2c_rpc_port: parseInt(e.target.value) || 6800 })}
                                style={{
                                  flex: 1,
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => copyToClipboard(String(settings.aria2c_rpc_port), 'rpc_port')}
                                style={{
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: copiedField === 'rpc_port' ? '#34d399' : '#a1a1aa',
                                  cursor: 'pointer',
                                }}
                                title="Copy RPC Port"
                              >
                                <Copy style={{ width: '15px', height: '15px' }} />
                              </button>
                            </div>
                          </div>

                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>RPC Secret:</label>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <input
                                type="text"
                                value={settings.aria2c_secret}
                                onChange={(e) => setSettings({ ...settings, aria2c_secret: e.target.value })}
                                style={{
                                  flex: 1,
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => copyToClipboard(settings.aria2c_secret, 'rpc_secret')}
                                style={{
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: copiedField === 'rpc_secret' ? '#34d399' : '#a1a1aa',
                                  cursor: 'pointer',
                                }}
                                title="Copy RPC Secret"
                              >
                                <Copy style={{ width: '15px', height: '15px' }} />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Listen Ports (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Listen Ports:</span>
                            <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                          </div>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px' }}>
                            <input
                              type="checkbox"
                              checked={settings.enable_upnp}
                              onChange={(e) => setSettings({ ...settings, enable_upnp: e.target.checked })}
                              style={{ accentColor: '#0284c7' }}
                            />
                            <span>UPnP / NAT-PMP</span>
                          </label>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>BT Listen Port:</label>
                            <input
                              type="number"
                              min="1024"
                              max="65535"
                              value={settings.bt_listen_port}
                              onChange={(e) => setSettings({ ...settings, bt_listen_port: parseInt(e.target.value) || 21301 })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                              }}
                            />
                          </div>

                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>DHT Listen Port:</label>
                            <input
                              type="number"
                              min="1024"
                              max="65535"
                              value={settings.dht_listen_port}
                              onChange={(e) => setSettings({ ...settings, dht_listen_port: parseInt(e.target.value) || 26701 })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                              }}
                            />
                          </div>
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Protocols (Local Browser Registration) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Protocols (Register as default browser handler):</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#581c87', color: '#d8b4fe' }}>Local Browser</span>
                        </div>
                        <div style={{ display: 'flex', gap: '12px' }}>
                          <button
                            type="button"
                            onClick={() => handleProtocolRegister('magnet')}
                            style={{
                              padding: '8px 14px',
                              backgroundColor: '#27272a',
                              border: '1px solid #3f3f46',
                              borderRadius: '6px',
                              color: '#38bdf8',
                              cursor: 'pointer',
                              fontSize: '13px',
                              fontWeight: 500,
                            }}
                          >
                            Register Magnet [ magnet:// ]
                          </button>
                        </div>
                      </div>
                    </>
                  )}

                  {/* TAB 3: LAB / DEVELOPER */}
                  {activeTab === 'lab' && (
                    <>
                      {/* User-Agent (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Mock User-Agent:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <textarea
                          rows={3}
                          value={settings.user_agent}
                          onChange={(e) => setSettings({ ...settings, user_agent: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '8px 10px',
                            backgroundColor: '#27272a',
                            border: '1px solid #3f3f46',
                            borderRadius: '6px',
                            color: '#ffffff',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            boxSizing: 'border-box',
                            marginBottom: '8px',
                          }}
                        />
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {[
                            { name: 'Aria2', ua: 'aria2/1.37.0' },
                            { name: 'Transmission', ua: 'Transmission/4.0.5' },
                            { name: 'Chrome', ua: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
                            { name: 'du', ua: 'du/1.0' },
                          ].map((p) => (
                            <button
                              key={p.name}
                              type="button"
                              onClick={() => setSettings({ ...settings, user_agent: p.ua })}
                              style={{
                                padding: '4px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '4px',
                                color: '#a1a1aa',
                                fontSize: '12px',
                                cursor: 'pointer',
                              }}
                            >
                              {p.name}
                            </button>
                          ))}
                        </div>
                      </div>

                      <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '4px 0' }} />

                      {/* Developer Paths & Logs (Centralized Shared) */}
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>Developer & Engine Paths:</span>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#0369a1', color: '#bae6fd' }}>Shared Engine</span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Custom aria2.conf path:</label>
                            <input
                              type="text"
                              value={settings.aria2_conf_path}
                              onChange={(e) => setSettings({ ...settings, aria2_conf_path: e.target.value })}
                              placeholder="/opt/Motrix/resources/engine/aria2.conf"
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                                boxSizing: 'border-box',
                              }}
                            />
                          </div>

                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Download session path:</label>
                            <input
                              type="text"
                              value={settings.session_path}
                              onChange={(e) => setSettings({ ...settings, session_path: e.target.value })}
                              placeholder="/downloads/download.session"
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#27272a',
                                border: '1px solid #3f3f46',
                                borderRadius: '6px',
                                color: '#ffffff',
                                fontSize: '13px',
                                boxSizing: 'border-box',
                              }}
                            />
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: '12px' }}>
                            <div>
                              <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>App log path:</label>
                              <input
                                type="text"
                                value={settings.log_path}
                                onChange={(e) => setSettings({ ...settings, log_path: e.target.value })}
                                placeholder="/downloads/download_manager.log"
                                style={{
                                  width: '100%',
                                  padding: '8px 10px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                  boxSizing: 'border-box',
                                }}
                              />
                            </div>

                            <div>
                              <label style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '4px' }}>Log Level:</label>
                              <select
                                value={settings.log_level}
                                onChange={(e) => setSettings({ ...settings, log_level: e.target.value })}
                                style={{
                                  width: '100%',
                                  padding: '8px',
                                  backgroundColor: '#27272a',
                                  border: '1px solid #3f3f46',
                                  borderRadius: '6px',
                                  color: '#ffffff',
                                  fontSize: '13px',
                                  boxSizing: 'border-box',
                                }}
                              >
                                <option value="warn">warn</option>
                                <option value="info">info</option>
                                <option value="debug">debug</option>
                                <option value="error">error</option>
                              </select>
                            </div>
                          </div>
                        </div>

                        {/* Reset Actions */}
                        <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                          <button
                            type="button"
                            onClick={handleResetSession}
                            disabled={actionLoading === 'session'}
                            style={{
                              padding: '8px 14px',
                              backgroundColor: '#27272a',
                              color: '#fbbf24',
                              border: '1px solid #d97706',
                              borderRadius: '6px',
                              fontSize: '13px',
                              cursor: 'pointer',
                              fontWeight: 500,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <RotateCcw style={{ width: '14px', height: '14px' }} />
                            <span>Reset download session</span>
                          </button>

                          <button
                            type="button"
                            onClick={handleFactoryReset}
                            disabled={actionLoading === 'factory'}
                            style={{
                              padding: '8px 14px',
                              backgroundColor: '#27272a',
                              color: '#f87171',
                              border: '1px solid #ef4444',
                              borderRadius: '6px',
                              fontSize: '13px',
                              cursor: 'pointer',
                              fontWeight: 500,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <Trash2 style={{ width: '14px', height: '14px' }} />
                            <span>Factory Reset</span>
                          </button>
                        </div>
                      </div>
                    </>
                  )}

                  {/* TAB 4: COOKIES & AUTH */}
                  {activeTab === 'cookies' && (
                    <>
                      <div style={{ backgroundColor: '#202024', padding: '16px', borderRadius: '8px', border: '1px solid #27272a' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: '#fafafa' }}>Extracted Cookie Cache</div>
                            <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                              {cookieStatus?.has_cached_cookies ? (
                                <span style={{ color: '#34d399' }}>Cookies cached (Last updated: {cookieStatus.cached_cookie_age})</span>
                              ) : (
                                <span style={{ color: '#fbbf24' }}>No cookies currently cached</span>
                              )}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={handleClearCookies}
                            disabled={actionLoading === 'cookies'}
                            style={{
                              padding: '6px 12px',
                              backgroundColor: '#27272a',
                              color: '#f87171',
                              border: '1px solid #ef4444',
                              borderRadius: '6px',
                              fontSize: '12px',
                              cursor: 'pointer',
                            }}
                          >
                            Clear Cached Cookies
                          </button>
                        </div>
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#f4f4f5', marginBottom: '6px' }}>
                          Cookie Cache Expiration (seconds)
                        </label>
                        <input
                          type="number"
                          value={settings.cookie_max_age}
                          onChange={(e) => setSettings({ ...settings, cookie_max_age: parseInt(e.target.value) || 86400 })}
                          style={{
                            width: '240px',
                            padding: '8px 12px',
                            backgroundColor: '#27272a',
                            border: '1px solid #3f3f46',
                            borderRadius: '6px',
                            color: '#ffffff',
                            fontSize: '13px',
                          }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#f4f4f5', marginBottom: '6px' }}>
                          Manual Cookie File Path (Optional)
                        </label>
                        <input
                          type="text"
                          value={settings.cookie_manual_path || ''}
                          onChange={(e) => setSettings({ ...settings, cookie_manual_path: e.target.value || null })}
                          placeholder="/path/to/cookies.txt"
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            backgroundColor: '#27272a',
                            border: '1px solid #3f3f46',
                            borderRadius: '6px',
                            color: '#ffffff',
                            fontSize: '13px',
                            boxSizing: 'border-box',
                          }}
                        />
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* Bottom Action Footer */}
            <div style={{
              padding: '14px 20px',
              borderTop: '1px solid #27272a',
              backgroundColor: '#202024',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              {/* Legend Badges */}
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0284c7' }} />
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>Shared Engine (Syncs with TUI & Backend)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#a855f7' }} />
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>Local Browser (This device only)</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  onClick={onClose}
                  style={{
                    padding: '8px 18px',
                    backgroundColor: '#27272a',
                    color: '#d4d4d8',
                    border: '1px solid #3f3f46',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontWeight: 500,
                  }}
                >
                  Discard
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  style={{
                    padding: '8px 20px',
                    backgroundColor: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Save style={{ width: '15px', height: '15px' }} />
                  <span>{saving ? 'Saving...' : 'Save & Apply'}</span>
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
