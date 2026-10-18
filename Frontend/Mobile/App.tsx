import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet, Text, View, FlatList, TextInput,
  TouchableOpacity, SafeAreaView, StatusBar, Alert, Modal
} from 'react-native';
import type { DownloadItem, DownloadStats } from './src/types';

const DEFAULT_SERVER_URL = 'http://10.0.2.2:8000';

export default function App() {
  const [serverUrl, setServerUrl] = useState(DEFAULT_SERVER_URL);
  const [isEditingServer, setIsEditingServer] = useState(false);
  const [tempServerUrl, setTempServerUrl] = useState(DEFAULT_SERVER_URL);
  const [isConnected, setIsConnected] = useState(false);
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [stats, setStats] = useState<DownloadStats | null>(null);
  const [inputUrl, setInputUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);

      const res = await fetch(`${serverUrl}/api/downloads`, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        setDownloads(data);
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }

      const statsRes = await fetch(`${serverUrl}/api/stats`);
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch {
      setIsConnected(false);
    }
  }, [serverUrl]);

  useEffect(() => {
    fetchItems();
    const interval = setInterval(fetchItems, 3000);
    return () => clearInterval(interval);
  }, [fetchItems]);

  const handleAdd = async () => {
    if (!inputUrl.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${serverUrl}/api/downloads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: inputUrl.trim(), quality: 'best' }),
      });
      if (res.ok) {
        setInputUrl('');
        fetchItems();
      } else {
        Alert.alert('Error', 'Failed to add download');
      }
    } catch {
      Alert.alert(
        'Backend Not Reachable',
        `Cannot connect to Sharky backend at:\n${serverUrl}\n\nPlease ensure your Python backend server is running on the host:\n\n./.venv/bin/python Backend/run.py server\n\nOr tap the server status button above to configure the host address.`
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSaveServer = () => {
    let clean = tempServerUrl.trim();
    if (clean && !clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = `http://${clean}`;
    }
    setServerUrl(clean || DEFAULT_SERVER_URL);
    setIsEditingServer(false);
  };

  const renderItem = ({ item }: { item: DownloadItem }) => (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.typeTag}>[{item.download_type.toUpperCase()}]</Text>
        <Text style={styles.title} numberOfLines={1}>{item.title}</Text>
      </View>
      <View style={styles.progressBar}>
        <View style={[styles.progressFill, { width: `${item.progress || 0}%` }]} />
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.metaText}>{item.status}</Text>
        <Text style={styles.metaText}>{item.download_speed || '0 B/s'}</Text>
        <Text style={styles.metaText}>{(item.progress || 0).toFixed(0)}%</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View>
            <Text style={styles.headerTitle}>SHARKY MOBILE</Text>
            <Text style={styles.headerSubtitle}>Remote Download Monitor</Text>
          </View>
          <TouchableOpacity
            style={[styles.connectionBadge, isConnected ? styles.badgeConnected : styles.badgeDisconnected]}
            onPress={() => {
              setTempServerUrl(serverUrl);
              setIsEditingServer(true);
            }}
          >
            <View style={[styles.statusDot, isConnected ? styles.dotConnected : styles.dotDisconnected]} />
            <Text style={styles.connectionText}>
              {isConnected ? 'Connected' : 'Offline'}
            </Text>
          </TouchableOpacity>
        </View>

        {!isConnected && (
          <TouchableOpacity
            style={styles.offlineBanner}
            onPress={() => {
              setTempServerUrl(serverUrl);
              setIsEditingServer(true);
            }}
          >
            <Text style={styles.offlineBannerText}>
              ⚠️ Backend offline ({serverUrl}). Tap to change server address.
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {stats && (
        <View style={styles.statsRow}>
          <Text style={styles.statPill}>Active: {stats.downloading}</Text>
          <Text style={styles.statPill}>Pending: {stats.pending}</Text>
          <Text style={styles.statPill}>Done: {stats.completed}</Text>
        </View>
      )}

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Paste URL or magnet link..."
          placeholderTextColor="#64748b"
          value={inputUrl}
          onChangeText={setInputUrl}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TouchableOpacity style={styles.addButton} onPress={handleAdd} disabled={loading}>
          <Text style={styles.addButtonText}>{loading ? '...' : 'Add'}</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={downloads}
        keyExtractor={item => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No downloads active. Paste a URL above to start.</Text>
        }
      />

      {/* Server Configuration Modal */}
      <Modal visible={isEditingServer} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Backend Server Address</Text>
            <Text style={styles.modalDescription}>
              Configure the host URL for your Sharky Python backend service:
            </Text>

            <TextInput
              style={styles.modalInput}
              value={tempServerUrl}
              onChangeText={setTempServerUrl}
              placeholder="e.g. http://10.0.2.2:8000"
              placeholderTextColor="#64748b"
              autoCapitalize="none"
              autoCorrect={false}
            />

            <View style={styles.presetContainer}>
              <Text style={styles.presetLabel}>Presets:</Text>
              <TouchableOpacity
                style={styles.presetPill}
                onPress={() => setTempServerUrl('http://10.0.2.2:8000')}
              >
                <Text style={styles.presetText}>Android Emulator (10.0.2.2)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.presetPill}
                onPress={() => setTempServerUrl('http://localhost:8000')}
              >
                <Text style={styles.presetText}>Localhost / iOS (8000)</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.modalCancelButton}
                onPress={() => setIsEditingServer(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSaveButton}
                onPress={handleSaveServer}
              >
                <Text style={styles.modalSaveText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0f19' },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  headerTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#f1f5f9' },
  headerSubtitle: { fontSize: 12, color: '#94a3b8', marginTop: 2 },
  connectionBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, borderWidth: 1 },
  badgeConnected: { backgroundColor: 'rgba(16, 185, 129, 0.1)', borderColor: '#10b981' },
  badgeDisconnected: { backgroundColor: 'rgba(239, 68, 68, 0.1)', borderColor: '#ef4444' },
  statusDot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  dotConnected: { backgroundColor: '#10b981' },
  dotDisconnected: { backgroundColor: '#ef4444' },
  connectionText: { fontSize: 11, fontWeight: '600', color: '#f1f5f9' },
  offlineBanner: { marginTop: 10, backgroundColor: 'rgba(239, 68, 68, 0.15)', borderWidth: 1, borderColor: '#ef4444', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 10 },
  offlineBannerText: { color: '#fca5a5', fontSize: 11, fontWeight: '500' },
  statsRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingTop: 12 },
  statPill: { backgroundColor: '#1e293b', color: '#38bdf8', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, fontSize: 12, fontWeight: '600' },
  inputContainer: { flexDirection: 'row', gap: 8, padding: 16 },
  input: { flex: 1, backgroundColor: '#1e293b', color: 'white', borderRadius: 8, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: '#334155' },
  addButton: { backgroundColor: '#0284c7', borderRadius: 8, paddingHorizontal: 16, justifyContent: 'center', alignItems: 'center' },
  addButtonText: { color: 'white', fontWeight: 'bold' },
  list: { padding: 16, gap: 12 },
  card: { backgroundColor: '#0f172a', padding: 14, borderRadius: 8, borderWidth: 1, borderColor: '#1e293b' },
  row: { flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 8 },
  typeTag: { color: '#38bdf8', fontSize: 11, fontWeight: 'bold' },
  title: { color: '#f1f5f9', fontWeight: '600', fontSize: 14, flex: 1 },
  progressBar: { height: 6, backgroundColor: '#1e293b', borderRadius: 3, overflow: 'hidden', marginVertical: 6 },
  progressFill: { height: '100%', backgroundColor: '#0284c7' },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  metaText: { color: '#94a3b8', fontSize: 12 },
  emptyText: { color: '#64748b', textAlign: 'center', marginTop: 40 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { width: '100%', backgroundColor: '#0f172a', borderRadius: 12, padding: 20, borderWidth: 1, borderColor: '#334155' },
  modalTitle: { fontSize: 18, fontWeight: 'bold', color: '#f1f5f9', marginBottom: 8 },
  modalDescription: { fontSize: 13, color: '#94a3b8', marginBottom: 14, lineHeight: 18 },
  modalInput: { backgroundColor: '#1e293b', color: 'white', borderRadius: 8, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: '#334155', marginBottom: 14 },
  presetContainer: { marginBottom: 18 },
  presetLabel: { color: '#94a3b8', fontSize: 12, marginBottom: 6 },
  presetPill: { backgroundColor: '#1e293b', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 6, marginBottom: 6, borderWidth: 1, borderColor: '#334155' },
  presetText: { color: '#38bdf8', fontSize: 12 },
  modalButtons: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10 },
  modalCancelButton: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6 },
  modalCancelText: { color: '#94a3b8', fontWeight: '600' },
  modalSaveButton: { backgroundColor: '#0284c7', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 6 },
  modalSaveText: { color: 'white', fontWeight: 'bold' },
});
