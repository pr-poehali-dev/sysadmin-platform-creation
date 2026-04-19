import { useState, useEffect, useCallback } from 'react';
import Icon from '@/components/ui/icon';

const PROXY_LOGS_URL = 'https://functions.poehali.dev/66527f53-af98-4478-a252-71e4fff6ae25';

interface LogEntry {
  id: number;
  target: string;
  status: number;
  response: string;
  ts: string;
}

function statusColor(code: number | null): string {
  if (!code) return 'status-idle';
  if (code >= 200 && code < 300) return 'status-ok';
  if (code >= 400 && code < 500) return 'status-warn';
  return 'status-err';
}

function formatTs(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function truncate(str: string, n = 60): string {
  return str.length > n ? str.slice(0, n) + '…' : str;
}

export default function MonitoringPage() {
  const [token, setToken]   = useState('');
  const [logs, setLogs]     = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);

  const fetchLogs = useCallback(async () => {
    if (!token.trim()) { setError('Введи ADMIN_TOKEN'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(PROXY_LOGS_URL, {
        headers: { 'Authorization': `Bearer ${token.trim()}` }
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || `Ошибка ${res.status}`); return; }
      setLogs(data.logs || []);
    } catch {
      setError('Не удалось получить логи');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    fetchLogs();
    const t = setInterval(fetchLogs, 30000);
    return () => clearInterval(t);
  }, [fetchLogs, token]);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-light tracking-tight text-foreground">Мониторинг</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Лог прокси-запросов · обновляется каждые 30 с
        </p>
      </div>

      {/* Token input */}
      <div className="border border-border bg-card px-6 py-5">
        <div className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
          Авторизация
        </div>
        <div className="flex gap-3">
          <input
            type="password"
            value={token}
            onChange={e => setToken(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchLogs()}
            placeholder="ADMIN_TOKEN"
            className="flex-1 bg-background border border-border text-sm mono px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
          />
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="px-5 py-2 text-sm mono bg-primary text-primary-foreground hover:bg-primary/80 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <Icon name="Loader" size={14} className="animate-spin" /> : <Icon name="RefreshCw" size={14} />}
            {loading ? 'Загрузка…' : 'Загрузить'}
          </button>
        </div>
        {error && (
          <p className="text-xs mono status-err mt-2 flex items-center gap-1">
            <Icon name="AlertCircle" size={12} />
            {error}
          </p>
        )}
      </div>

      {/* Stats bar */}
      {logs.length > 0 && (
        <div className="grid grid-cols-3 gap-px bg-border">
          {[
            { label: 'Всего записей',  value: logs.length },
            { label: '2xx успешных',   value: logs.filter(l => l.status >= 200 && l.status < 300).length },
            { label: 'Ошибок (4xx/5xx/0)', value: logs.filter(l => l.status === 0 || l.status >= 400).length },
          ].map(s => (
            <div key={s.label} className="bg-card px-6 py-4">
              <div className="text-xs text-muted-foreground mono mb-1">{s.label}</div>
              <div className="text-2xl font-light text-foreground">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      {logs.length > 0 && (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-4 py-3 text-left text-xs mono uppercase tracking-widest text-muted-foreground font-normal w-12">#</th>
                <th className="px-4 py-3 text-left text-xs mono uppercase tracking-widest text-muted-foreground font-normal">Цель</th>
                <th className="px-4 py-3 text-left text-xs mono uppercase tracking-widest text-muted-foreground font-normal w-20">Статус</th>
                <th className="px-4 py-3 text-left text-xs mono uppercase tracking-widest text-muted-foreground font-normal">Ответ</th>
                <th className="px-4 py-3 text-left text-xs mono uppercase tracking-widest text-muted-foreground font-normal w-36">Время</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <>
                  <tr
                    key={log.id}
                    className="border-b border-border hover:bg-muted/20 cursor-pointer transition-colors"
                    onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                  >
                    <td className="px-4 py-3 text-xs mono text-muted-foreground">{log.id}</td>
                    <td className="px-4 py-3 text-xs mono text-foreground/80 max-w-xs">
                      {truncate(log.target, 50)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs mono font-medium ${statusColor(log.status)}`}>
                        {log.status || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs mono text-muted-foreground max-w-xs">
                      {truncate(log.response || '—', 50)}
                    </td>
                    <td className="px-4 py-3 text-xs mono text-muted-foreground">
                      {log.ts ? formatTs(log.ts) : '—'}
                    </td>
                  </tr>
                  {expanded === log.id && (
                    <tr key={`${log.id}-exp`} className="bg-muted/10">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="space-y-2">
                          <div className="text-xs mono text-muted-foreground">
                            <span className="text-foreground/50">target: </span>{log.target}
                          </div>
                          <pre className="text-xs mono text-muted-foreground bg-background border border-border p-3 overflow-x-auto whitespace-pre-wrap break-all">
                            {log.response || '(пусто)'}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {logs.length === 0 && !loading && !error && token && (
        <div className="border border-border bg-card px-6 py-12 text-center">
          <Icon name="Inbox" size={24} className="text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Логов пока нет</p>
        </div>
      )}
    </div>
  );
}
