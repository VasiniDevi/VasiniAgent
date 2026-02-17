import { useEffect, useState } from 'react';
import api from '../api';
import StatsCard from '../components/StatsCard';

interface PeriodSummary {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  by_model: { model: string; input_tokens: number; output_tokens: number; cost_usd: number }[];
}

interface TokenRecord {
  id: number;
  user_id: number;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  created_at: number;
}

interface TokenUsageResponse {
  days: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  records: TokenRecord[];
}

export default function Monitoring() {
  const [summary, setSummary] = useState<Record<string, PeriodSummary> | null>(null);
  const [usage, setUsage] = useState<TokenUsageResponse | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api<Record<string, PeriodSummary>>('/api/monitoring/summary'),
      api<TokenUsageResponse>('/api/monitoring/tokens?days=30'),
    ]).then(([s, u]) => {
      setSummary(s);
      setUsage(u);
    }).catch(e => setError(e.message));
  }, []);

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;
  if (!summary || !usage) return <div className="text-gray-500 p-4">Loading monitoring data...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">Monitoring</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard
          title="Today"
          value={`$${summary.today?.cost_usd?.toFixed(4) ?? '0.0000'}`}
          subtitle={`${(summary.today?.input_tokens + summary.today?.output_tokens || 0).toLocaleString()} tokens`}
        />
        <StatsCard
          title="This Week"
          value={`$${summary.week?.cost_usd?.toFixed(4) ?? '0.0000'}`}
          subtitle={`${(summary.week?.input_tokens + summary.week?.output_tokens || 0).toLocaleString()} tokens`}
        />
        <StatsCard
          title="This Month"
          value={`$${summary.month?.cost_usd?.toFixed(4) ?? '0.0000'}`}
          subtitle={`${(summary.month?.input_tokens + summary.month?.output_tokens || 0).toLocaleString()} tokens`}
        />
      </div>

      {/* By model breakdown */}
      {summary.month?.by_model && summary.month.by_model.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Cost by Model (30 days)</h3>
          <div className="space-y-2">
            {summary.month.by_model.map(m => (
              <div key={m.model} className="flex items-center justify-between text-sm">
                <span className="font-mono text-gray-700">{m.model}</span>
                <div className="flex gap-6 text-gray-500">
                  <span>{m.input_tokens.toLocaleString()} in</span>
                  <span>{m.output_tokens.toLocaleString()} out</span>
                  <span className="font-medium text-gray-900">${m.cost_usd.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Token usage table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-sm font-medium text-gray-700">
            Token Usage Log ({usage.records.length} records, 30 days)
          </h3>
          <p className="text-xs text-gray-400 mt-1">
            Total: {usage.total_input_tokens.toLocaleString()} input + {usage.total_output_tokens.toLocaleString()} output = ${usage.total_cost_usd.toFixed(4)}
          </p>
        </div>
        <div className="max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Time</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">User</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Model</th>
                <th className="text-right px-4 py-2 font-medium text-gray-500">Input</th>
                <th className="text-right px-4 py-2 font-medium text-gray-500">Output</th>
                <th className="text-right px-4 py-2 font-medium text-gray-500">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {usage.records.map(r => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500">
                    {new Date(r.created_at * 1000).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-mono text-gray-700">{r.user_id}</td>
                  <td className="px-4 py-2 font-mono text-gray-700 text-xs">{r.model}</td>
                  <td className="px-4 py-2 text-right text-gray-700">{r.input_tokens.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-gray-700">{r.output_tokens.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right font-medium text-gray-900">${r.cost_usd.toFixed(6)}</td>
                </tr>
              ))}
              {usage.records.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No token usage records found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
