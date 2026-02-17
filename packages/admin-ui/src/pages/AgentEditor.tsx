import { useEffect, useState } from 'react';
import api from '../api';
import YamlEditor from '../components/YamlEditor';

const LAYERS = ['soul', 'role', 'tools', 'guardrails', 'memory', 'workflow'] as const;
type Layer = typeof LAYERS[number];

export default function AgentEditor() {
  const [activeTab, setActiveTab] = useState<Layer>('soul');
  const [contents, setContents] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    api<Record<string, any>>('/api/agent/pack')
      .then(data => {
        const yamlContents: Record<string, string> = {};
        for (const layer of LAYERS) {
          // Convert the JSON object back to YAML-like readable text
          yamlContents[layer] = data[layer]
            ? JSON.stringify(data[layer], null, 2)
            : '';
        }
        setContents(yamlContents);
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const handleSave = async (layer: Layer, content: string) => {
    // Parse the JSON content back to an object for the API
    let parsed: any;
    try {
      parsed = JSON.parse(content);
    } catch {
      throw new Error('Invalid JSON format. Please check your syntax.');
    }
    await api(`/api/agent/pack/${layer}`, {
      method: 'PUT',
      body: JSON.stringify({ content: parsed }),
    });
    setContents(prev => ({ ...prev, [layer]: content }));
  };

  const handlePreview = async () => {
    setPreviewLoading(true);
    setShowPreview(true);
    try {
      const data = await api<{ system_prompt: string }>('/api/agent/prompt-preview');
      setPreview(data.system_prompt);
    } catch (e: any) {
      setPreview(`Error: ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  if (loading) return <div className="text-gray-500 p-4">Loading agent pack...</div>;
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800">Agent Editor</h2>
        <button onClick={handlePreview}
          className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm hover:bg-gray-900">
          Preview System Prompt
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
        {LAYERS.map(layer => (
          <button key={layer} onClick={() => setActiveTab(layer)}
            className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors ${
              activeTab === layer
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}>{layer}</button>
        ))}
      </div>

      {/* Editor */}
      <YamlEditor
        key={activeTab}
        content={contents[activeTab] || ''}
        onSave={(content) => handleSave(activeTab, content)}
      />

      {/* Prompt preview modal */}
      {showPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-8">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800">System Prompt Preview</h3>
              <button onClick={() => setShowPreview(false)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {previewLoading ? (
                <p className="text-gray-500">Generating preview...</p>
              ) : (
                <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono bg-gray-50 rounded-lg p-4">
                  {preview}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
