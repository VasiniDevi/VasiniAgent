import { useEffect, useState } from 'react';
import api from '../api';
import StatsCard from '../components/StatsCard';
import MoodChart from '../components/MoodChart';
import MessageList from '../components/MessageList';

interface DashboardData {
  total_users: number;
  active_today: number;
  avg_mood_7d: number | null;
  tokens_today: number;
  status_counts: Record<string, number>;
  mood_trend: { date: string; avg_score: number }[];
  recent_messages: { user_id: number; role: string; content: string; created_at: number }[];
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<DashboardData>('/api/dashboard')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;
  if (!data) return <div className="text-gray-500 p-4">Loading dashboard...</div>;

  // Convert mood_trend to MoodChart format (date string -> unix timestamp)
  const moodChartData = data.mood_trend.map(d => ({
    score: d.avg_score,
    created_at: new Date(d.date).getTime() / 1000,
  }));

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">Dashboard</h2>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard title="Total Users" value={data.total_users} />
        <StatsCard title="Active Today" value={data.active_today} />
        <StatsCard title="Avg Mood (7d)" value={data.avg_mood_7d ?? 'N/A'} subtitle="Scale 1-10" />
        <StatsCard title="Tokens Today" value={data.tokens_today.toLocaleString()} />
      </div>

      {/* Status counts */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-3">User Status Distribution</h3>
        <div className="flex flex-wrap gap-3">
          {Object.entries(data.status_counts).map(([status, count]) => (
            <div key={status} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg">
              <span className={`inline-block w-2 h-2 rounded-full ${
                status === 'active' ? 'bg-green-500' :
                status === 'onboarding' ? 'bg-yellow-500' :
                status === 'paused' ? 'bg-gray-400' :
                status === 'crisis' ? 'bg-red-500' : 'bg-blue-500'
              }`} />
              <span className="text-sm text-gray-700 capitalize">{status}</span>
              <span className="text-sm font-semibold text-gray-900">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Mood trend chart */}
      {moodChartData.length > 0 && <MoodChart data={moodChartData} />}

      {/* Recent messages */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">Recent Messages</h3>
        {data.recent_messages.length > 0 ? (
          <MessageList messages={data.recent_messages} />
        ) : (
          <p className="text-sm text-gray-400">No messages yet.</p>
        )}
      </div>
    </div>
  );
}
