import React, { useState } from 'react';
import {
  Download, Play, Pause, Square, RotateCcw, Trash2, Plus, Wifi, WifiOff,
  Film, File, HardDrive, CheckCircle2, AlertCircle, Clock, Settings
} from 'lucide-react';
import {
  useSharkyWebSocket, startDownloads, pauseDownloads, resumeDownloads,
  stopDownloads, retryFailedDownloads, clearCompletedDownloads, removeDownload,
  addDownload, addBatchDownloads
} from './api';
import type { AddDownloadPayload } from './types';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const { downloads, stats, connected } = useSharkyWebSocket();
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [batchInput, setBatchInput] = useState('');
  const [quality, setQuality] = useState('best');
  const [expectedHash, setExpectedHash] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isBatchMode) {
        const urls = batchInput.split('\n').map(s => s.trim()).filter(Boolean);
        if (urls.length > 0) {
          await addBatchDownloads({ urls, quality });
        }
      } else if (urlInput.trim()) {
        const payload: AddDownloadPayload = {
          url: urlInput.trim(),
          quality,
          expected_hash: expectedHash.trim() || undefined,
        };
        await addDownload(payload);
      }
      setShowAddModal(false);
      setUrlInput('');
      setBatchInput('');
      setExpectedHash('');
    } catch (err: any) {
      alert(err.message || 'Error adding download');
    } finally {
      setLoading(false);
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'video': return <Film className="w-4 h-4 text-rose-400" />;
      case 'torrent': return <HardDrive className="w-4 h-4 text-emerald-400" />;
      default: return <File className="w-4 h-4 text-sky-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'downloading':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/20 text-blue-300 border border-blue-500/30">Downloading</span>;
      case 'completed':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Completed</span>;
      case 'failed':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/20 text-rose-300 border border-rose-500/30">Failed</span>;
      case 'paused':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30">Paused</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/20 text-slate-300 border border-slate-500/30">Pending</span>;
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0b0f19', color: '#f1f5f9', fontFamily: 'system-ui, sans-serif' }}>
      {/* Top Navbar */}
      <header style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#0f172a', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'linear-gradient(135deg, #0284c7, #38bdf8)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Download style={{ width: '20px', height: '20px', color: '#ffffff' }} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', letterSpacing: '-0.02em' }}>SHARKY</h1>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>High-Performance Download Engine</p>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '8px', fontSize: '12px', color: connected ? '#34d399' : '#f87171' }}>
            {connected ? <Wifi style={{ width: '14px', height: '14px' }} /> : <WifiOff style={{ width: '14px', height: '14px' }} />}
            <span>{connected ? 'Live Sync' : 'Reconnecting...'}</span>
          </div>

          <button onClick={() => setShowAddModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#0284c7', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
            <Plus style={{ width: '16px', height: '16px' }} /> Add Download
          </button>

          <button onClick={() => setShowSettingsModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', backgroundColor: '#1e293b', color: '#38bdf8', border: '1px solid #0284c7', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }} title="Open System Settings">
            <Settings style={{ width: '15px', height: '15px' }} /> Settings
          </button>

          <button onClick={() => startDownloads()} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
            <Play style={{ width: '14px', height: '14px' }} /> Start
          </button>

          <button onClick={() => pauseDownloads()} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', backgroundColor: '#d97706', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
            <Pause style={{ width: '14px', height: '14px' }} /> Pause
          </button>

          <button onClick={() => resumeDownloads()} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
            <RotateCcw style={{ width: '14px', height: '14px' }} /> Resume
          </button>

          <button onClick={() => stopDownloads()} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
            <Square style={{ width: '14px', height: '14px' }} /> Stop
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
              <span>Downloading</span>
              <Download style={{ width: '16px', height: '16px', color: '#38bdf8' }} />
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', marginTop: '8px', color: '#38bdf8' }}>{stats?.downloading || 0}</div>
          </div>

          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
              <span>Pending</span>
              <Clock style={{ width: '16px', height: '16px', color: '#facc15' }} />
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', marginTop: '8px', color: '#facc15' }}>{stats?.pending || 0}</div>
          </div>

          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
              <span>Completed</span>
              <CheckCircle2 style={{ width: '16px', height: '16px', color: '#4ade80' }} />
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', marginTop: '8px', color: '#4ade80' }}>{stats?.completed || 0}</div>
          </div>

          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
              <span>Failed</span>
              <AlertCircle style={{ width: '16px', height: '16px', color: '#f87171' }} />
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', marginTop: '8px', color: '#f87171' }}>{stats?.failed || 0}</div>
          </div>
        </div>

        {/* Section Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Active & Queued Downloads</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => setShowSettingsModal(true)} style={{ padding: '6px 12px', fontSize: '12px', backgroundColor: '#1e293b', color: '#38bdf8', border: '1px solid #0284c7', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 500 }} title="Open System Settings">
              <Settings style={{ width: '13px', height: '13px' }} /> Settings
            </button>
            <button onClick={() => retryFailedDownloads()} style={{ padding: '6px 12px', fontSize: '12px', backgroundColor: '#1e293b', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer' }}>
              Retry Failed
            </button>
            <button onClick={() => clearCompletedDownloads()} style={{ padding: '6px 12px', fontSize: '12px', backgroundColor: '#1e293b', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer' }}>
              Clear Completed
            </button>
          </div>
        </div>

        {/* Downloads Table */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#1e293b', color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                <th style={{ padding: '12px 16px', width: '50px' }}>Type</th>
                <th style={{ padding: '12px 16px' }}>Title</th>
                <th style={{ padding: '12px 16px', width: '120px' }}>Status</th>
                <th style={{ padding: '12px 16px', width: '220px' }}>Progress</th>
                <th style={{ padding: '12px 16px', width: '110px' }}>Speed</th>
                <th style={{ padding: '12px 16px', width: '80px' }}>ETA</th>
                <th style={{ padding: '12px 16px', width: '60px' }}></th>
              </tr>
            </thead>
            <tbody>
              {downloads.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>
                    No downloads found. Click "Add Download" to get started.
                  </td>
                </tr>
              ) : (
                downloads.map((item) => (
                  <tr key={item.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={{ padding: '14px 16px' }}>{getTypeIcon(item.download_type)}</td>
                    <td style={{ padding: '14px 16px', fontWeight: 500, maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <div title={item.title}>{item.title}</div>
                      <div style={{ fontSize: '12px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.url}</div>
                      {item.error_message && (
                        <div style={{ fontSize: '11px', color: '#f87171', marginTop: '2px' }} title={item.error_message}>
                          {item.error_message}
                        </div>
                      )}
                      {item.status === 'completed' && (
                        <div style={{ fontSize: '11px', color: '#34d399', marginTop: '2px' }}>
                          ✓ Saved to downloads folder
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px' }}>{getStatusBadge(item.status)}</td>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ flex: 1, height: '8px', backgroundColor: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                          <div style={{ width: `${item.progress || 0}%`, height: '100%', backgroundColor: item.status === 'completed' ? '#10b981' : '#0284c7', transition: 'width 0.3s ease' }} />
                        </div>
                        <span style={{ fontSize: '12px', color: '#94a3b8', width: '40px', textAlign: 'right' }}>{(item.progress || 0).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: '13px', color: '#38bdf8' }}>{item.download_speed || '-'}</td>
                    <td style={{ padding: '14px 16px', fontSize: '13px', color: '#94a3b8' }}>{item.eta || '-'}</td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                        {item.status === 'completed' && (
                          <a
                            href={`/api/downloads/${item.id}/file`}
                            download
                            style={{
                              color: '#38bdf8',
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              padding: '4px',
                              borderRadius: '4px',
                              textDecoration: 'none',
                              cursor: 'pointer',
                            }}
                            title="Download / Open file"
                          >
                            <Download style={{ width: '16px', height: '16px' }} />
                          </a>
                        )}
                        <button onClick={() => removeDownload(item.id)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px' }} title="Delete download">
                          <Trash2 style={{ width: '16px', height: '16px' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>

      {/* Add Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '12px', width: '100%', maxWidth: '500px', padding: '24px' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 'bold' }}>Add Download</h3>

            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <button onClick={() => setIsBatchMode(false)} style={{ flex: 1, padding: '8px', border: 'none', borderRadius: '6px', cursor: 'pointer', backgroundColor: !isBatchMode ? '#0284c7' : '#1e293b', color: 'white', fontWeight: 600 }}>
                Single URL
              </button>
              <button onClick={() => setIsBatchMode(true)} style={{ flex: 1, padding: '8px', border: 'none', borderRadius: '6px', cursor: 'pointer', backgroundColor: isBatchMode ? '#0284c7' : '#1e293b', color: 'white', fontWeight: 600 }}>
                Batch Import
              </button>
            </div>

            <form onSubmit={handleAddSubmit}>
              {isBatchMode ? (
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>URLs (one per line):</label>
                  <textarea rows={5} value={batchInput} onChange={e => setBatchInput(e.target.value)} placeholder="https://example.com/file1.zip&#10;https://example.com/file2.zip" style={{ width: '100%', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: 'white', resize: 'vertical' }} />
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Target URL / Magnet Link:</label>
                    <input type="text" value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder="https://... or magnet:?..." style={{ width: '100%', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: 'white' }} required />
                  </div>
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Expected Checksum (SHA256/MD5, optional):</label>
                    <input type="text" value={expectedHash} onChange={e => setExpectedHash(e.target.value)} placeholder="e.g. 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8" style={{ width: '100%', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: 'white' }} />
                  </div>
                </>
              )}

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Video Quality (for YouTube / Video streams):</label>
                <select value={quality} onChange={e => setQuality(e.target.value)} style={{ width: '100%', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: 'white' }}>
                  <option value="best">Best Available</option>
                  <option value="1080p (Full HD)">1080p (Full HD)</option>
                  <option value="720p (HD)">720p (HD)</option>
                  <option value="480p (SD)">480p (SD)</option>
                  <option value="Audio Only (High Quality)">Audio Only (High Quality)</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" onClick={() => setShowAddModal(false)} style={{ padding: '8px 16px', backgroundColor: '#1e293b', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer' }}>
                  Cancel
                </button>
                <button type="submit" disabled={loading} style={{ padding: '8px 16px', backgroundColor: '#0284c7', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
                  {loading ? 'Adding...' : 'Add to Queue'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </div>
  );
}
