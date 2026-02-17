import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import StatsCard from '../components/StatsCard';
import MoodChart from '../components/MoodChart';
import MessageList from '../components/MessageList';

interface UserInfo {
  user_id: number;
  status: string;
  checkin_interval: number;
  missed_checkins: number;
  quiet_start: number;
  quiet_end: number;
  updated_at: number | null;
  message_count: number;
  mood_count: number;
  last_mood: { score: number; note: string | null; created_at: number } | null;
}

interface MoodEntry {
  id: number;
  score: number;
  note: string | null;
  created_at: number;
}

interface Message {
  id: number;
  role: string;
  content: string;
  created_at: number;
}

const INTERVALS = [2, 4, 8, 24];

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [moods, setMoods] = useState<MoodEntry[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const load = () => {
    if (!id) return;
    Promise.all([
      api<UserInfo>(`/api/users/${id}`),
      api<{ moods: MoodEntry[] }>(`/api/moods/${id}?days=30`),
      api<{ messages: Message[] }>(`/api/messages/${id}?limit=100`),
    ]).then(([u, m, msgs]) => {
      setUser(u);
      setMoods(m.moods);
      setMessages(msgs.messages);
    }).catch(e => setError(e.message));
  };

  useEffect(load, [id]);

  const setInterval = async (hours: number) => {
    try {
      await api(`/api/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ checkin_interval: hours }),
      });
      setActionMsg(`Check-in interval set to ${hours}h`);
      setTimeout(() => setActionMsg(''), 2000);
      load();
    } catch (e: any) {
      setActionMsg(`Error: ${e.message}`);
    }
  };

  const resetMissed = async () => {
    try {
      await api(`/api/users/${id}/reset-checkins`, { method: 'POST' });
      setActionMsg('Missed check-ins reset');
      setTimeout(() => setActionMsg(''), 2000);
      load();
    } catch (e: any) {
      setActionMsg(`Error: ${e.message}`);
    }
  };

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;
  if (!user) return <div className="text-gray-500 p-4">Loading user...</div>;

  const moodChartData = [...moods].reverse().map(m => ({ score: m.score, created_at: m.created_at }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/users" className="text-blue-600 hover:text-blue-800 text-sm">&larr; Back</Link>
        <h2 className="text-xl font-bold text-gray-800">User {user.user_id}</h2>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
          user.status === 'active' ? 'bg-green-100 text-green-700' :
          user.status === 'crisis' ? 'bg-red-100 text-red-700' :
          user.status === 'paused' ? 'bg-gray-100 text-gray-600' :
          'bg-yellow-100 text-yellow-700'
        }`}>{user.status}</span>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard title="Messages" value={user.message_count} />
        <StatsCard title="Mood Entries" value={user.mood_count} />
        <StatsCard title="Last Mood" value={user.last_mood?.score ?? 'N/A'}
          subtitle={user.last_mood?.note || undefined} />
        <StatsCard title="Missed Check-ins" value={user.missed_checkins} />
      </div>

      {/* Check-in interval buttons */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Check-in Interval</h3>
        <div className="flex items-center gap-2">
          {INTERVALS.map(h => (
            <button key={h} onClick={() => setInterval(h)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${
                user.checkin_interval === h
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}>{h}h</button>
          ))}
          <button onClick={resetMissed}
            className="ml-4 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-700 border border-red-200 hover:bg-red-100">
            Reset Missed
          </button>
          {actionMsg && <span className="text-sm text-green-600 ml-2">{actionMsg}</span>}
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Quiet hours: {user.quiet_start}:00 - {user.quiet_end}:00
        </p>
      </div>

      {/* Mood chart */}
      {moodChartData.length > 0 && <MoodChart data={moodChartData} />}

      {/* Conversation history */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">Conversation History</h3>
        {messages.length > 0 ? (
          <MessageList messages={messages} />
        ) : (
          <p className="text-sm text-gray-400">No messages yet.</p>
        )}
      </div>
    </div>
  );
}
