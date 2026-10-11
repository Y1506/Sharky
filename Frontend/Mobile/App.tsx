import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, FlatList, TextInput,
  TouchableOpacity, SafeAreaView, StatusBar, Alert
} from 'react-native';
import type { DownloadItem, DownloadStats } from './src/types';

// Default backend host (configured for local dev or emulator)
const SERVER_URL = 'http://10.0.2.2:8000'; // or http://localhost:8000 for iOS

export default function App() {
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [stats, setStats] = useState<DownloadStats | null>(null);
  const [inputUrl, setInputUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchItems = async () => {
    try {
      const res = await fetch(`${SERVER_URL}/api/downloads`);
      if (res.ok) {
        const data = await res.json();
        setDownloads(data);
      }
      const statsRes = await fetch(`${SERVER_URL}/api/stats`);
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch {
      // Offline / server not running
    }
  };

  useEffect(() => {
    fetchItems();
    const interval = setInterval(fetchItems, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleAdd = async () => {
    if (!inputUrl.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/api/downloads`, {
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
      Alert.alert('Network Error', 'Cannot connect to Sharky backend service');
    } finally {
      setLoading(false);
    }
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
        <Text style={styles.headerTitle}>SHARKY MOBILE</Text>
        <Text style={styles.headerSubtitle}>Remote Download Monitor</Text>
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0f19' },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#f1f5f9' },
  headerSubtitle: { fontSize: 12, color: '#94a3b8', marginTop: 2 },
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
});
