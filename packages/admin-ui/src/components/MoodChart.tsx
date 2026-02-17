import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function MoodChart({ data }: { data: { score: number; created_at: number }[] }) {
  const formatted = data.map(d => ({ ...d, date: new Date(d.created_at * 1000).toLocaleDateString() }));
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-medium text-gray-700 mb-4">Mood Trend (30d)</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={formatted}>
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={[1, 10]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
