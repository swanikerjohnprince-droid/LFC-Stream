import { useEffect, useState, type FormEvent } from 'react';
import { Activity, ArrowLeft, CalendarDays, Clapperboard, Cloud, FileVideo, Folder, FolderOpen, LayoutDashboard, ListVideo, LoaderCircle, Radio, Search, Settings, MonitorPlay } from 'lucide-react';

type DriveFile = {
  id: string; name: string; mime_type: string; kind: 'folder' | 'video' | 'file';
  size?: string; modified_time?: string; thumbnail_url?: string;
};
const nav = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Media library', icon: FolderOpen },
  { label: 'Live channels', icon: Radio },
  { label: 'Schedules', icon: CalendarDays },
  { label: 'Playlists', icon: ListVideo },
];
const API = '/api/v1';

function formatBytes(value?: string) {
  if (!value) return '—';
  const size = Number(value);
  if (!Number.isFinite(size)) return '—';
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function App() {
  const [page, setPage] = useState('Overview');
  const [connected, setConnected] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [loginUsername, setLoginUsername] = useState('admin');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [checking, setChecking] = useState(true);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [folderId, setFolderId] = useState<string | undefined>();
  const [folderTrail, setFolderTrail] = useState<{id: string; name: string}[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedVideo, setSelectedVideo] = useState<DriveFile | null>(null);
  const [nextPageToken, setNextPageToken] = useState<string | undefined>();

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setLoggingIn(true); setLoginError('');
    try {
      const response = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Sign-in failed.');
      setAuthenticated(true);
      setLoginPassword('');
      await checkDrive();
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : 'Sign-in failed.');
    } finally { setLoggingIn(false); }
  }

  async function signOut() {
    await fetch(`${API}/auth/logout`, { method: 'POST' });
    setAuthenticated(false); setConnected(false); setFiles([]);
    setSelectedVideo(null);
  }

  async function checkDrive() {
    try {
      const response = await fetch(`${API}/drive/status`);
      if (response.status === 401) { setAuthenticated(false); return; }
      if (!response.ok) throw new Error('Could not check Google Drive connection.');
      const data = await response.json();
      setAuthenticated(true);
      setConnected(Boolean(data.connected));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'API unavailable.');
    } finally { setChecking(false); }
  }

  async function loadFiles(parent = folderId, term = search, pageToken?: string, append = false) {
    setLoading(true); setError('');
    try {
      const params = new URLSearchParams();
      if (parent) params.set('parent_id', parent);
      if (term.trim()) params.set('search', term.trim());
      if (pageToken) params.set('page_token', pageToken);
      const response = await fetch(`${API}/drive/files?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load Drive files.');
      setFiles(current => append ? [...current, ...(data.files || [])] : (data.files || []));
      setNextPageToken(data.next_page_token || undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load Drive files.');
    } finally { setLoading(false); }
  }

  useEffect(() => {
    checkDrive();
    const params = new URLSearchParams(window.location.search);
    if (params.get('drive') === 'connected') {
      setPage('Media library');
      window.history.replaceState({}, '', window.location.pathname);
    } else if (params.get('drive_error')) {
      setError('Google authorization was cancelled or denied.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (page === 'Media library' && connected) loadFiles(undefined, '');
  }, [page, connected]);

  function openFolder(file: DriveFile) {
    setFolderId(file.id);
    setFolderTrail(current => [...current, { id: file.id, name: file.name }]);
    loadFiles(file.id, '');
    setSearch('');
  }
  function goToTrail(index: number) {
    const next = folderTrail.slice(0, index + 1);
    setFolderTrail(next);
    const id = next[index]?.id;
    setFolderId(id);
    loadFiles(id, '');
    setSearch('');
  }
  function connectDrive() { window.location.href = `${API}/auth/google/start`; }
  async function disconnectDrive() {
    if (!window.confirm('Disconnect Google Drive from LFC Stream?')) return;
    await fetch(`${API}/drive/disconnect`, { method: 'POST' });
    setConnected(false); setFiles([]); setFolderId(undefined); setFolderTrail([]);
  }

  if (!authenticated && !checking) return <div className="login-screen"><form className="login-card" onSubmit={signIn}><div className="brand-mark"><Radio size={22}/></div><span className="eyebrow accent">PRIVATE BROADCAST WORKSPACE</span><h1>Welcome back.</h1><p>Sign in to manage your LFC Stream workspace.</p><label>Username<input autoComplete="username" value={loginUsername} onChange={e=>setLoginUsername(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required /></label>{loginError && <div className="error-banner">{loginError}</div>}<button className="primary login-submit" disabled={loggingIn}>{loggingIn ? <LoaderCircle className="spin" size={16}/> : null} Sign in</button><small>Single-admin access · Session expires after 12 hours</small></form></div>;
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Radio size={21}/></div><div><strong>LFC Stream</strong><span>Broadcast studio</span></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(({label, icon: Icon}) => <button onClick={() => setPage(label)} className={`nav-item ${page === label ? 'active' : ''}`} key={label}><Icon size={18}/><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><Settings size={18}/><span>Settings</span></button><div className="cloud-card"><Cloud size={18}/><div><b>Cloud control</b><small>Always-on broadcasting</small></div><span className="status-dot"/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="eyebrow">YOUR BROADCAST WORKSPACE</span><h1>{page}</h1></div><div className="top-actions"><span className="connection"><i/> API online</span><button className="secondary small" onClick={signOut}>Sign out</button><button className="avatar">LF</button></div></header>
      {page === 'Media library' ? <section className="library-page">
        <div className="library-heading"><div><h2>Google Drive library</h2><p>Browse your folders and choose video files for broadcasts.</p></div>{connected ? <button className="secondary" onClick={disconnectDrive}>Disconnect Drive</button> : null}</div>
        {error && <div className="error-banner">{error}</div>}
        {!connected ? <div className="drive-connect panel"><div className="drive-logo"><Cloud size={30}/></div><h3>Connect your Google Drive</h3><p>Authorize read-only access so LFC Stream can browse the videos you select for broadcasting. Your files stay in Drive.</p><button className="primary" onClick={connectDrive} disabled={checking}>{checking ? <LoaderCircle className="spin" size={16}/> : <Cloud size={16}/>} Connect Google Drive</button><small>Read-only permission · You can disconnect at any time</small></div> :
          <div className="panel drive-browser">
            <div className="browser-toolbar"><div className="breadcrumbs"><button onClick={() => {setFolderId(undefined);setFolderTrail([]);setSearch('');loadFiles(undefined, '');}}>My Drive</button>{folderTrail.map((f,i)=><span key={f.id}> / <button onClick={() => goToTrail(i)}>{f.name}</button></span>)}</div><form onSubmit={e=>{e.preventDefault();loadFiles(folderId,search);}} className="search-box"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search this folder"/></form></div>
            {loading ? <div className="browser-message"><LoaderCircle className="spin" size={22}/> Loading your Drive…</div> :
              files.length ? <div className="file-list">{files.map(file=><button className="file-row" key={file.id} onClick={()=>file.kind === 'folder' ? openFolder(file) : file.kind === 'video' ? setSelectedVideo(file) : undefined} disabled={file.kind === 'file'}><span className={`file-icon ${file.kind}`}>{file.kind === 'folder' ? <Folder size={18}/> : <FileVideo size={18}/>}</span><span className="file-name"><b>{file.name}</b><small>{file.kind === 'folder' ? 'Folder' : file.mime_type}</small></span><span className="file-size">{formatBytes(file.size)}</span></button>)}</div> :
              <div className="browser-message">No files found in this folder.</div>}{nextPageToken && <div className="load-more"><button className="secondary small" onClick={()=>loadFiles(folderId,search,nextPageToken,true)}>Load more files</button></div>}
          </div>}
      </section> : page === 'Overview' ? <>
        <section className="welcome"><div><div className="eyebrow accent">STREAMING, SIMPLIFIED</div><h2>Your broadcasts.<br/><em>Always on.</em></h2><p>Manage your Google Drive media, schedule broadcasts and run continuous channels from one cloud workspace.</p><div className="welcome-actions"><button className="primary" onClick={()=>setPage('Live channels')}><Radio size={17}/> Set up a channel</button><button className="secondary" onClick={()=>setPage('Media library')}><FolderOpen size={17}/> {connected ? 'Browse Google Drive' : 'Connect Google Drive'}</button></div></div><div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="play-card"><div className="play-icon"><Clapperboard size={30}/></div><span>YOUR MEDIA</span><b>One library.<br/>Every platform.</b><div className="platforms"><span><MonitorPlay size={16}/> YouTube</span><span className="tiktok">♪ TikTok</span></div></div></div></section>
        <section className="stats"><article><div className="stat-icon purple"><Radio size={18}/></div><span>ACTIVE CHANNELS</span><strong>0</strong><small>No broadcasts running</small></article><article><div className="stat-icon blue"><Clapperboard size={18}/></div><span>MEDIA ASSETS</span><strong>{connected ? 'Connected' : '—'}</strong><small>{connected ? 'Google Drive connected' : 'Connect Drive to browse videos'}</small></article><article><div className="stat-icon green"><CalendarDays size={18}/></div><span>UPCOMING SCHEDULES</span><strong>0</strong><small>Nothing scheduled yet</small></article><article><div className="stat-icon orange"><Activity size={18}/></div><span>DESTINATIONS</span><strong>0</strong><small>Connect a streaming destination</small></article></section>
        <section className="lower-grid"><article className="panel"><div className="panel-heading"><div><h3>Live channels</h3><p>Your continuous and scheduled broadcasts</p></div></div><div className="empty-state"><div className="empty-icon"><Radio size={23}/></div><b>No channels yet</b><p>Create a channel to start planning your first broadcast.</p><button className="secondary small" onClick={()=>setPage('Live channels')}>Create your first channel</button></div></article><article className="panel activity-panel"><div className="panel-heading"><div><h3>Recent activity</h3><p>Updates from your workspace</p></div></div><div className="activity-empty"><span className="activity-line"/><div><b>All quiet for now</b><p>Your broadcast activity will appear here.</p></div></div></article></section>
      </> : <section className="panel placeholder-page"><div className="empty-icon"><Radio size={23}/></div><h3>{page} are coming next</h3><p>This section will be connected as the broadcast engine is implemented.</p></section>}
      {selectedVideo && <div className="video-modal" role="dialog" aria-modal="true" aria-label={selectedVideo.name}><div className="video-modal-card"><div className="video-modal-head"><div><b>{selectedVideo.name}</b><small>Preview streamed progressively from Google Drive</small></div><button className="secondary small" onClick={()=>setSelectedVideo(null)}>Close</button></div><video controls autoPlay playsInline src={API + '/drive/files/' + selectedVideo.id + '/stream'} /></div></div>}
      <footer>LFC STREAM <span>·</span> CLOUD BROADCAST CONTROL <span className="version">EARLY ACCESS · 0.2.0</span></footer>
    </main>
  </div>;
}
