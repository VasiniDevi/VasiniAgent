export default function MessageList({ messages }: { messages: { role: string; content: string; created_at: number }[] }) {
  return (
    <div className="space-y-3 max-h-[500px] overflow-y-auto">
      {messages.map((m, i) => (
        <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-start' : 'items-end'}`}>
          <div className={`max-w-[75%] rounded-xl px-4 py-2 text-sm ${
            m.role === 'user' ? 'bg-gray-100 text-gray-800' : 'bg-blue-500 text-white'
          }`}>{m.content}</div>
          <span className="text-xs text-gray-400 mt-1">{new Date(m.created_at * 1000).toLocaleTimeString()}</span>
        </div>
      ))}
    </div>
  );
}
