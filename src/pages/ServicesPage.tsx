import Icon from '@/components/ui/icon';

const services = [
  {
    name: 'auth-proxy',
    desc: 'HTTP прокси с авторизацией через токен Lambda Runtime. Принимает target_url, выполняет GET-запрос от имени среды выполнения, логирует в БД.',
    status: 'ok',
    method: 'POST',
    runtime: 'Python 3.11',
    auth: 'ADMIN_TOKEN',
    db: true,
    params: ['target_url — URL назначения (string)'],
    returns: 'status — HTTP код ответа целевого сервиса',
  },
  {
    name: 'proxy-logs',
    desc: 'Возвращает последние 50 записей из таблицы proxy_log: цель, статус, ответ, временная метка.',
    status: 'ok',
    method: 'GET',
    runtime: 'Python 3.11',
    auth: 'ADMIN_TOKEN',
    db: true,
    params: [],
    returns: 'logs[] — массив записей proxy_log',
  },
];

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { dot: string; text: string; label: string }> = {
    ok:   { dot: 'dot-ok',   text: 'status-ok',   label: 'active' },
    warn: { dot: 'dot-warn', text: 'status-warn',  label: 'degraded' },
    err:  { dot: 'dot-err',  text: 'status-err',   label: 'error' },
    idle: { dot: 'dot-idle', text: 'status-idle',  label: 'idle' },
  };
  const c = cfg[status] || cfg.idle;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs mono ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot} ${status === 'ok' ? 'animate-pulse-dot' : ''}`} />
      {c.label}
    </span>
  );
}

export default function ServicesPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-light tracking-tight text-foreground">Сервисы</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {services.length} развёрнутых функции · все активны
        </p>
      </div>

      <div className="space-y-4">
        {services.map((s) => (
          <div key={s.name} className="border border-border bg-card">
            {/* Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-4">
                <StatusBadge status={s.status} />
                <h2 className="font-medium mono text-foreground">{s.name}</h2>
                <span className={`text-xs mono px-1.5 py-0.5 border ${
                  s.method === 'POST'
                    ? 'border-primary/30 text-primary bg-primary/5'
                    : 'border-muted-foreground/20 text-muted-foreground'
                }`}>
                  {s.method}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs mono text-muted-foreground">
                <span>{s.runtime}</span>
                {s.db && (
                  <span className="flex items-center gap-1">
                    <Icon name="Database" size={11} />
                    DB
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Icon name="ShieldCheck" size={11} />
                  {s.auth}
                </span>
              </div>
            </div>

            {/* Body */}
            <div className="px-6 py-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-3">
                <p className="text-sm text-muted-foreground">{s.desc}</p>
              </div>

              {s.params.length > 0 && (
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Параметры</div>
                  <ul className="space-y-1">
                    {s.params.map((p) => (
                      <li key={p} className="text-xs mono text-foreground/70">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className={s.params.length > 0 ? '' : 'lg:col-span-3'}>
                <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Возвращает</div>
                <div className="text-xs mono text-foreground/70">{s.returns}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Infrastructure note */}
      <div className="border border-border bg-muted/20 px-6 py-4">
        <div className="flex items-start gap-3">
          <Icon name="Info" size={14} className="text-muted-foreground mt-0.5 flex-shrink-0" />
          <p className="text-xs text-muted-foreground">
            Все функции защищены токеном <span className="mono">ADMIN_TOKEN</span>. Передавай его в заголовке{' '}
            <span className="mono">Authorization: Bearer {'<token>'}</span>. Запросы между функциями
            используют токен Lambda Runtime API, получаемый автоматически из среды выполнения.
          </p>
        </div>
      </div>
    </div>
  );
}
