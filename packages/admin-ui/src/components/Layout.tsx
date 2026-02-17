import { Link, Outlet, useLocation } from 'react-router-dom';

const NAV = [
  { path: '/', label: 'Dashboard', icon: '\u{1F4CA}' },
  { path: '/users', label: 'Users', icon: '\u{1F465}' },
  { path: '/agent', label: 'Agent', icon: '\u{1F9E0}' },
  { path: '/monitoring', label: 'Monitoring', icon: '\u{1F4C8}' },
  { path: '/settings', label: 'Settings', icon: '\u2699\uFE0F' },
];

export default function Layout() {
  const location = useLocation();
  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 p-4">
        <h1 className="text-lg font-bold mb-6 text-gray-800">Wellness Admin</h1>
        <nav className="space-y-1">
          {NAV.map(({ path, label, icon }) => (
            <Link key={path} to={path}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                location.pathname === path ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
              }`}>{icon} {label}</Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto p-6"><Outlet /></main>
    </div>
  );
}
