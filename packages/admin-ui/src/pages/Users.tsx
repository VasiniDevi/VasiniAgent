import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

interface User {
  user_id: number;
  status: string;
  missed_checkins: number;
  last_message_at: number;
  last_mood: number | null;
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  onboarding: 'bg-yellow-100 text-yellow-700',
  paused: 'bg-gray-100 text-gray-600',
  crisis: 'bg-red-100 text-red-700',
};

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api<User[]>('/api/users')
      .then(setUsers)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;
  if (!users.length && !error) return <div className="text-gray-500 p-4">Loading users...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">Users</h2>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">User ID</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Last Mood</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Missed Check-ins</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Last Active</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.map(u => (
              <tr key={u.user_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-gray-900">{u.user_id}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                    STATUS_COLORS[u.status] || 'bg-blue-100 text-blue-700'
                  }`}>{u.status}</span>
                </td>
                <td className="px-4 py-3 text-gray-700">{u.last_mood ?? '-'}</td>
                <td className="px-4 py-3">
                  <span className={u.missed_checkins > 2 ? 'text-red-600 font-medium' : 'text-gray-700'}>
                    {u.missed_checkins}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {u.last_message_at ? new Date(u.last_message_at * 1000).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-3">
                  <Link to={`/users/${u.user_id}`}
                    className="text-blue-600 hover:text-blue-800 text-xs font-medium">
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
