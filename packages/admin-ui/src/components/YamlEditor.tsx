import { useState } from 'react';

export default function YamlEditor({ content, onSave }: { content: string; onSave: (c: string) => Promise<void> }) {
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true); setError(''); setSaved(false);
    try { await onSave(value); setSaved(true); setTimeout(() => setSaved(false), 2000); }
    catch (e: any) { setError(e.message || 'Save failed'); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <textarea value={value} onChange={e => setValue(e.target.value)}
        className="w-full h-[500px] font-mono text-sm border border-gray-300 rounded-lg p-4 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
        spellCheck={false} />
      <div className="flex items-center gap-3 mt-3">
        <button onClick={handleSave} disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save & Validate'}
        </button>
        {saved && <span className="text-sm text-green-600">Saved!</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}
