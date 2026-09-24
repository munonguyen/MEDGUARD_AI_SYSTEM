import { useEffect, useState } from 'react';
import { Activity, Database, RefreshCw, ServerCog } from 'lucide-react';
import { CheckRow, StatusBadge } from '../components';

export function SystemModule({ api, tenantId }) {
  const [view, setView] = useState('readiness');
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = async (nextView = view) => {
    setBusy(true); setError(null);
    const paths = { readiness: '/v1/health/readiness', audit: '/v1/audit/events?limit=50', models: '/v1/models', metrics: '/metrics' };
    try { setData(await api.request(paths[nextView])); } catch (err) { setError(err); } finally { setBusy(false); }
  };
  useEffect(() => { load(view); }, [view, tenantId]);

  return <div className="system-panel">
    <div className="segmented system-tabs">
      <button type="button" className={view === 'readiness' ? 'active' : ''} onClick={() => setView('readiness')}>Readiness</button>
      <button type="button" className={view === 'audit' ? 'active' : ''} onClick={() => setView('audit')}>Audit</button>
      <button type="button" className={view === 'models' ? 'active' : ''} onClick={() => setView('models')}>Models</button>
      <button type="button" className={view === 'metrics' ? 'active' : ''} onClick={() => setView('metrics')}>Metrics</button>
    </div>
    <button className="secondary-button refresh-system" type="button" onClick={() => load()} disabled={busy}><RefreshCw className={busy ? 'spin' : ''} size={16} /> Làm mới</button>
    {error && <div className="inline-error">{error.code}: {error.message}</div>}
    {view === 'readiness' && data?.checks && <div className="system-list">
      <div className="system-summary"><div><ServerCog size={22} /><span>Môi trường</span><strong>{data.environment}</strong></div><StatusBadge value={data.status} /></div>
      {data.checks.map((check) => <CheckRow check={check} key={check.name} />)}
    </div>}
    {view === 'audit' && data?.events && <div className="audit-table">
      <div className="table-head"><span>Thời gian</span><span>Action</span><span>Request</span></div>
      {data.events.map((event, index) => <div className="table-row" key={`${event.request_id}-${index}`}><span>{new Date(event.created_at).toLocaleString('vi-VN')}</span><strong>{event.action}</strong><code>{event.request_id}</code></div>)}
      {!data.events.length && <div className="table-empty">Chưa có audit event</div>}
    </div>}
    {view === 'models' && data?.models && <div className="model-grid">{data.models.map((model) => <div className="model-card" key={model.name}><Database size={19} /><strong>{model.name}</strong><span>{model.version}</span><p>{model.purpose}</p><StatusBadge value={model.active ? 'active' : 'inactive'} /></div>)}</div>}
    {view === 'metrics' && typeof data === 'string' && <div className="metrics-view"><Activity size={20} /><pre>{data}</pre></div>}
  </div>;
}
