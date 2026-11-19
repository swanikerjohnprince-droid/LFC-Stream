import { Activity, CalendarDays, Clapperboard, Cloud, FolderOpen, LayoutDashboard, ListVideo, Radio, Settings, Youtube } from 'lucide-react';

const nav = [
  { label: 'Overview', icon: LayoutDashboard, active: true },
  { label: 'Media library', icon: FolderOpen },
  { label: 'Live channels', icon: Radio },
  { label: 'Schedules', icon: CalendarDays },
  { label: 'Playlists', icon: ListVideo },
];

export default function App() {
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Radio size={21}/></div><div><strong>LFC Stream</strong><span>Broadcast studio</span></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(({label, icon: Icon, active}) => <button className={`nav-item ${active ? 'active' : ''}`} key={label}><Icon size={18}/><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><Settings size={18}/><span>Settings</span></button><div className="cloud-card"><Cloud size={18}/><div><b>Cloud control</b><small>Always-on broadcasting</small></div><span className="status-dot"/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="eyebrow">YOUR BROADCAST WORKSPACE</span><h1>Overview</h1></div><div className="top-actions"><span className="connection"><i/> System ready</span><button className="avatar">LF</button></div></header>
      <section className="welcome"><div><div className="eyebrow accent">STREAMING, SIMPLIFIED</div><h2>Your broadcasts.<br/><em>Always on.</em></h2><p>Manage your Google Drive media, schedule broadcasts and run continuous channels from one cloud workspace.</p><div className="welcome-actions"><button className="primary"><Radio size={17}/> Set up a channel</button><button className="secondary"><FolderOpen size={17}/> Connect Google Drive</button></div></div><div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="play-card"><div className="play-icon"><Clapperboard size={30}/></div><span>YOUR MEDIA</span><b>One library.<br/>Every platform.</b><div className="platforms"><span><Youtube size={16}/> YouTube</span><span className="tiktok">♪ TikTok</span></div></div></div></section>
      <section className="stats"><article><div className="stat-icon purple"><Radio size={18}/></div><span>ACTIVE CHANNELS</span><strong>0</strong><small>No broadcasts running</small></article><article><div className="stat-icon blue"><Clapperboard size={18}/></div><span>MEDIA ASSETS</span><strong>—</strong><small>Connect Drive to browse videos</small></article><article><div className="stat-icon green"><CalendarDays size={18}/></div><span>UPCOMING SCHEDULES</span><strong>0</strong><small>Nothing scheduled yet</small></article><article><div className="stat-icon orange"><Activity size={18}/></div><span>DESTINATIONS</span><strong>0</strong><small>Connect a streaming destination</small></article></section>
      <section className="lower-grid"><article className="panel"><div className="panel-heading"><div><h3>Live channels</h3><p>Your continuous and scheduled broadcasts</p></div><button className="text-button">View all</button></div><div className="empty-state"><div className="empty-icon"><Radio size={23}/></div><b>No channels yet</b><p>Create a channel to start planning your first broadcast.</p><button className="secondary small">Create your first channel</button></div></article><article className="panel activity-panel"><div className="panel-heading"><div><h3>Recent activity</h3><p>Updates from your workspace</p></div></div><div className="activity-empty"><span className="activity-line"/><div><b>All quiet for now</b><p>Your broadcast activity will appear here.</p></div></div></article></section>
      <footer> LFC STREAM <span>·</span> CLOUD BROADCAST CONTROL <span className="version">EARLY ACCESS · 0.1.0</span></footer>
    </main>
  </div>;
}
