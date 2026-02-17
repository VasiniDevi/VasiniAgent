import { useEffect, useState } from 'react';
import api from '../api';

const SAFE_KEYS = [
  'CLAUDE_MODEL',
  'CHECKIN_INTERVAL_HOURS',
  'QUIET_HOURS_START',
  'QUIET_HOURS_END',
  'PACK_DIR',
  'DB_PATH',
  'ALLOWED_USER_IDS',
  'ELEVENLABS_VOICE_ID',
  'ELEVENLABS_MODEL',
];

const SECRET_KEYS = [
  'TELEGRAM_BOT_TOKEN',
  'ANTHROPIC_API_KEY',
  'OPENAI_API_KEY',
  'ELEVENLABS_API_KEY',
];

export default function Settings() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<{ config: Record<string, string> }>('/api/config')
      .then(data => {
        setConfig(data.config);
        // Initialize edits with only safe keys
        const editableValues: Record<string, string> = {};
        for (const key of SAFE_KEYS) {
          if (data.config[key] !== undefined) {
            editableValues[key] = data.config[key];
          }
        }
        setEdits(editableValues);
      })
      .catch(e => setError(e.message));
  }, []);

  const handleChange = (key: string, value: string) => {
    setEdits(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true); setError(''); setSaved(false);
    try {
      // Only send keys that actually changed
      const changed: Record<string, string> = {};
      for (const [key, value] of Object.entries(edits)) {
        if (config[key] !== value) {
          changed[key] = value;
        }
      }
      if (Object.keys(changed).length === 0) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        setSaving(false);
        return;
      }
      await api('/api/config', {
        method: 'PATCH',
        body: JSON.stringify({ values: changed }),
      });
      setConfig(prev => ({ ...prev, ...changed }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!Object.keys(config).length && !error) {
    return <div className="text-gray-500 p-4">Loading settings...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">Settings</h2>

      {error && <div className="text-red-600 text-sm bg-red-50 p-3 rounded-lg">{error}</div>}

      {/* Editable config fields */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">Configuration</h3>
        <div className="space-y-4">
          {SAFE_KEYS.map(key => (
            <div key={key} className="flex flex-col sm:flex-row sm:items-center gap-2">
              <label className="w-56 text-sm font-mono text-gray-600 shrink-0">{key}</label>
              <input
                type="text"
                value={edits[key] ?? ''}
                onChange={e => handleChange(key, e.target.value)}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder={`Set ${key}`}
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-5">
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {saved && <span className="text-sm text-green-600">Saved!</span>}
        </div>
      </div>

      {/* Read-only API keys */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">API Keys (read-only)</h3>
        <div className="space-y-3">
          {SECRET_KEYS.map(key => (
            <div key={key} className="flex flex-col sm:flex-row sm:items-center gap-2">
              <label className="w-56 text-sm font-mono text-gray-600 shrink-0">{key}</label>
              <input
                type="text"
                value={config[key] ?? '(not set)'}
                readOnly
                className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-gray-50 text-gray-500 cursor-not-allowed"
              />
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3">
          API keys are masked for security. Update them directly in the .env file on the server.
        </p>
      </div>
    </div>
  );
}
