import React, { useState, useEffect } from 'react';
import {
  X, Save, RefreshCw, Check, AlertCircle,
  HardDrive, Gauge, Shield, Cookie, Folder, Cpu
} from 'lucide-react';
import { fetchSettings, updateSettings, fetchCookieStatus, clearCookies } from '../api';
import type { AppSettings, CookieStatus } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  autoSaveToDevice: boolean;
  onToggleAutoSave: (val: boolean) => void;
}

export default function SettingsModal({ isOpen, onClose, autoSaveToDevice, onToggleAutoSave }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'general' | 'engine' | 'cookies'>('general');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [clearingCookies, setClearingCookies] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const [settings, setSettings] = useState<AppSettings>({
    download_dir: '',
    concurrent_downloads: 10,
    download_speed_limit: 0,
    aria2c_rpc_port: 6800,
    aria2c_secret: '',
    qbittorrent_host: 'http://localhost:8080',
    qbittorrent_username: 'admin',
    cookie_max_age: 86400,
    cookie_manual_path: null,
    cookie_browser_order: ['zen', 'brave'],
  });

  const [cookieStatus, setCookieStatus] = useState<CookieStatus | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadData();
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
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to load settings', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const res = await updateSettings(settings);
      setSettings(res.settings);
      setMessage({ text: 'Settings saved successfully!', type: 'success' });
      setTimeout(() => {
        setMessage(null);
      }, 3000);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to save settings', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleClearCookies = async () => {
    setClearingCookies(true);
    try {
      await clearCookies();
      const updatedStatus = await fetchCookieStatus();
      setCookieStatus(updatedStatus);
      setMessage({ text: 'Cached cookies cleared successfully', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to clear cookies', type: 'error' });
    } finally {
      setClearingCookies(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 60,
      backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        backgroundColor: '#0f172a',
        border: '1px solid #334155',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '680px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu style={{ width: '20px', height: '20px', color: '#38bdf8' }} />
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#f8fafc' }}>System Settings</h2>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X style={{ width: '20px', height: '20px' }} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #1e293b',
          backgroundColor: '#0b0f19',
          padding: '0 16px',
        }}>
          <button
            type="button"
            onClick={() => setActiveTab('general')}
            style={{
              padding: '12px 16px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'general' ? '2px solid #38bdf8' : '2px solid transparent',
              color: activeTab === 'general' ? '#38bdf8' : '#94a3b8',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '13px',
            }}
          >
            <Folder style={{ width: '15px', height: '15px' }} /> General
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('engine')}
            style={{
              padding: '12px 16px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'engine' ? '2px solid #38bdf8' : '2px solid transparent',
              color: activeTab === 'engine' ? '#38bdf8' : '#94a3b8',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '13px',
            }}
          >
            <Gauge style={{ width: '15px', height: '15px' }} /> Engines & Speed
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cookies')}
            style={{
              padding: '12px 16px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'cookies' ? '2px solid #38bdf8' : '2px solid transparent',
              color: activeTab === 'cookies' ? '#38bdf8' : '#94a3b8',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '13px',
            }}
          >
            <Cookie style={{ width: '15px', height: '15px' }} /> Cookies & Auth
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

        {/* Content Body */}
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div style={{ padding: '20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                <RefreshCw style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite', margin: '0 auto 8px' }} />
                <div>Loading configuration...</div>
              </div>
            ) : (
              <>
                {/* General Tab */}
                {activeTab === 'general' && (
                  <>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#f1f5f9', marginBottom: '6px' }}>
                        Download Directory
                      </label>
                      <input
                        type="text"
                        value={settings.download_dir}
                        onChange={(e) => setSettings({ ...settings, download_dir: e.target.value })}
                        placeholder="/downloads"
                        style={{
                          width: '100%',
                          padding: '10px 12px',
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          color: '#ffffff',
                          fontSize: '14px',
                          boxSizing: 'border-box',
                        }}
                      />
                      <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                        Base folder where all subdirectories (videos, audio, files, torrents) are stored on the server.
                      </span>
                    </div>

                    <div style={{ backgroundColor: '#1e293b', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ paddingRight: '16px' }}>
                          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
                            Auto-Save to Device / Browser
                          </label>
                          <span style={{ fontSize: '12px', color: '#94a3b8', marginTop: '3px', display: 'block' }}>
                            Automatically trigger browser file download to your device's Downloads directory as soon as the download finishes.
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          checked={autoSaveToDevice}
                          onChange={(e) => onToggleAutoSave(e.target.checked)}
                          style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: '#38bdf8' }}
                        />
                      </div>
                    </div>

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <label style={{ fontSize: '13px', fontWeight: 500, color: '#f1f5f9' }}>
                          Max Concurrent Downloads
                        </label>
                        <span style={{ fontSize: '13px', color: '#38bdf8', fontWeight: 600 }}>
                          {settings.concurrent_downloads}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="32"
                        value={settings.concurrent_downloads}
                        onChange={(e) => setSettings({ ...settings, concurrent_downloads: parseInt(e.target.value, 10) })}
                        style={{ width: '100%', cursor: 'pointer' }}
                      />
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#64748b' }}>
                        <span>1</span>
                        <span>16</span>
                        <span>32</span>
                      </div>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#f1f5f9', marginBottom: '6px' }}>
                        Download Speed Limit
                      </label>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '10px' }}>
                        {[
                          { label: 'Unlimited', val: 0 },
                          { label: '1 MB/s', val: 1048576 },
                          { label: '5 MB/s', val: 5242880 },
                          { label: '10 MB/s', val: 10485760 },
                        ].map((preset) => (
                          <button
                            key={preset.label}
                            type="button"
                            onClick={() => setSettings({ ...settings, download_speed_limit: preset.val })}
                            style={{
                              padding: '8px',
                              backgroundColor: settings.download_speed_limit === preset.val ? '#0284c7' : '#1e293b',
                              color: settings.download_speed_limit === preset.val ? '#ffffff' : '#94a3b8',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              fontSize: '12px',
                              cursor: 'pointer',
                              fontWeight: 500,
                            }}
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <input
                          type="number"
                          min="0"
                          value={settings.download_speed_limit}
                          onChange={(e) => setSettings({ ...settings, download_speed_limit: parseInt(e.target.value, 10) || 0 })}
                          style={{
                            width: '180px',
                            padding: '8px 12px',
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '6px',
                            color: '#ffffff',
                            fontSize: '13px',
                          }}
                        />
                        <span style={{ fontSize: '12px', color: '#94a3b8' }}>bytes / second (0 = unlimited)</span>
                      </div>
                    </div>
                  </>
                )}

                {/* Engines & Speed Tab */}
                {activeTab === 'engine' && (
                  <>
                    <div style={{ backgroundColor: '#1e293b', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <HardDrive style={{ width: '16px', height: '16px' }} /> aria2c Acceleration RPC
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>RPC Port</label>
                          <input
                            type="number"
                            value={settings.aria2c_rpc_port}
                            onChange={(e) => setSettings({ ...settings, aria2c_rpc_port: parseInt(e.target.value, 10) || 6800 })}
                            style={{
                              width: '100%',
                              padding: '8px 10px',
                              backgroundColor: '#0f172a',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              color: '#fff',
                              boxSizing: 'border-box',
                            }}
                          />
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>RPC Secret</label>
                          <input
                            type="password"
                            value={settings.aria2c_secret}
                            onChange={(e) => setSettings({ ...settings, aria2c_secret: e.target.value })}
                            placeholder="Secret token"
                            style={{
                              width: '100%',
                              padding: '8px 10px',
                              backgroundColor: '#0f172a',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              color: '#fff',
                              boxSizing: 'border-box',
                            }}
                          />
                        </div>
                      </div>
                    </div>

                    <div style={{ backgroundColor: '#1e293b', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Shield style={{ width: '16px', height: '16px' }} /> qBittorrent Client Web UI
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>WebUI Host</label>
                          <input
                            type="text"
                            value={settings.qbittorrent_host}
                            onChange={(e) => setSettings({ ...settings, qbittorrent_host: e.target.value })}
                            placeholder="http://localhost:8080"
                            style={{
                              width: '100%',
                              padding: '8px 10px',
                              backgroundColor: '#0f172a',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              color: '#fff',
                              boxSizing: 'border-box',
                            }}
                          />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Username</label>
                            <input
                              type="text"
                              value={settings.qbittorrent_username}
                              onChange={(e) => setSettings({ ...settings, qbittorrent_username: e.target.value })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#0f172a',
                                border: '1px solid #334155',
                                borderRadius: '6px',
                                color: '#fff',
                                boxSizing: 'border-box',
                              }}
                            />
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Password</label>
                            <input
                              type="password"
                              placeholder="••••••••"
                              onChange={(e) => setSettings({ ...settings, qbittorrent_password: e.target.value })}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                backgroundColor: '#0f172a',
                                border: '1px solid #334155',
                                borderRadius: '6px',
                                color: '#fff',
                                boxSizing: 'border-box',
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {/* Cookies Tab */}
                {activeTab === 'cookies' && (
                  <>
                    <div style={{ backgroundColor: '#1e293b', padding: '14px', borderRadius: '8px', border: '1px solid #334155' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <h4 style={{ margin: 0, fontSize: '14px', color: '#facc15', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Cookie style={{ width: '16px', height: '16px' }} /> Browser Cookie Status
                        </h4>
                        <button
                          type="button"
                          onClick={handleClearCookies}
                          disabled={clearingCookies}
                          style={{
                            padding: '6px 12px',
                            backgroundColor: '#334155',
                            color: '#f87171',
                            border: '1px solid #475569',
                            borderRadius: '6px',
                            fontSize: '12px',
                            cursor: 'pointer',
                            fontWeight: 500,
                          }}
                        >
                          {clearingCookies ? 'Clearing...' : 'Clear Cached Cookies'}
                        </button>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', fontSize: '12px' }}>
                        <div style={{ padding: '8px 12px', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                          <span style={{ color: '#94a3b8' }}>Cached Cookies: </span>
                          <span style={{ color: cookieStatus?.has_cached_cookies ? '#34d399' : '#94a3b8', fontWeight: 600 }}>
                            {cookieStatus?.has_cached_cookies ? 'Active' : 'None'}
                          </span>
                        </div>
                        <div style={{ padding: '8px 12px', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                          <span style={{ color: '#94a3b8' }}>Cookie Freshness: </span>
                          <span style={{ color: cookieStatus?.cached_cookie_fresh ? '#34d399' : '#facc15', fontWeight: 600 }}>
                            {cookieStatus?.cached_cookie_fresh ? 'Fresh' : cookieStatus?.has_cached_cookies ? 'Stale' : 'N/A'}
                          </span>
                        </div>
                        <div style={{ padding: '8px 12px', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                          <span style={{ color: '#94a3b8' }}>Zen Browser: </span>
                          <span style={{ color: cookieStatus?.zen_available ? '#34d399' : '#64748b', fontWeight: 600 }}>
                            {cookieStatus?.zen_available ? 'Detected' : 'Not found'}
                          </span>
                        </div>
                        <div style={{ padding: '8px 12px', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                          <span style={{ color: '#94a3b8' }}>Brave Browser: </span>
                          <span style={{ color: cookieStatus?.brave_available ? '#34d399' : '#64748b', fontWeight: 600 }}>
                            {cookieStatus?.brave_available ? 'Detected' : 'Not found'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#f1f5f9', marginBottom: '6px' }}>
                        Manual Cookie File Path
                      </label>
                      <input
                        type="text"
                        value={settings.cookie_manual_path || ''}
                        onChange={(e) => setSettings({ ...settings, cookie_manual_path: e.target.value || null })}
                        placeholder="/path/to/cookies.txt (Netscape format)"
                        style={{
                          width: '100%',
                          padding: '10px 12px',
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          color: '#ffffff',
                          fontSize: '13px',
                          boxSizing: 'border-box',
                        }}
                      />
                      <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                        Optional manual path to Netscape-format cookie export for authenticated streams.
                      </span>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#f1f5f9', marginBottom: '6px' }}>
                        Cookie Max Age (Seconds)
                      </label>
                      <input
                        type="number"
                        min="300"
                        value={settings.cookie_max_age}
                        onChange={(e) => setSettings({ ...settings, cookie_max_age: parseInt(e.target.value, 10) || 86400 })}
                        style={{
                          width: '180px',
                          padding: '8px 12px',
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          color: '#ffffff',
                          fontSize: '13px',
                        }}
                      />
                      <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                        Default is 86400 (24 hours).
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {/* Footer Controls */}
          <div style={{
            padding: '16px 20px',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
            backgroundColor: '#0b0f19',
          }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                backgroundColor: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #334155',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '13px',
              }}
            >
              Close
            </button>
            <button
              type="submit"
              disabled={saving || loading}
              style={{
                padding: '8px 18px',
                backgroundColor: '#0284c7',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Save style={{ width: '15px', height: '15px' }} />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
