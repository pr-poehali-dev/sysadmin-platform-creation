import Icon from '@/components/ui/icon';

type Page = 'home' | 'services' | 'monitoring';

const metrics = [
  { label: 'Активных сервисов', value: '2', icon: 'Box', status: 'ok' },
  { label: 'Запросов за сутки', value: '—', icon: 'ArrowRightLeft', status: 'idle' },
  { label: 'Ошибок за сутки',  value: '—', icon: 'AlertCircle', status: 'idle' },
  { label: 'Среднее время',    value: '—', icon: 'Timer', status: 'idle' },
];

const services = [
  { name: 'auth-proxy',  desc: 'HTTP прокси с авторизацией', status: 'ok',  type: 'Python' },
  { name: 'proxy-logs',  desc: 'Чтение логов прокси',       status: 'ok',  type: 'Python' },
];

export default function HomePage({ onNavigate }: { onNavigate: (p: Page) => void }) {
  return (
    <div className="max-w-4xl mx-auto space-y-10">
      {/* Hero */}
      <div>
        <h1 className="text-2xl font-light tracking-tight text-foreground">
          Панель управления
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Платформа управления микросервисами · auth-proxy gateway
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-border">
        {metrics.map((m) => (
          <div key={m.label} className="bg-card px-6 py-5">
            <div className={`text-xs mono mb-2 ${m.status === 'ok' ? 'status-ok' : 'status-idle'}`}>
              <Icon name={m.icon} size={13} className="inline mr-1" />
              {m.label}
            </div>
            <div className={`text-3xl font-light ${m.status === 'ok' ? 'text-foreground' : 'text-muted-foreground'}`}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* Services summary */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
            Функции
          </h2>
          <button
            onClick={() => onNavigate('services')}
            className="text-xs mono text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            Все сервисы <Icon name="ArrowRight" size={12} />
          </button>
        </div>
        <div className="space-y-px bg-border border border-border">
          {services.map((s) => (
            <div key={s.name} className="bg-card px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-1.5 h-1.5 rounded-full ${s.status === 'ok' ? 'dot-ok animate-pulse-dot' : 'dot-idle'}`} />
                <div>
                  <div className="text-sm font-medium mono text-foreground">{s.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{s.desc}</div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs mono text-muted-foreground">{s.type}</span>
                <span className={`text-xs mono ${s.status === 'ok' ? 'status-ok' : 'status-idle'}`}>
                  {s.status === 'ok' ? 'active' : 'idle'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auth-proxy info */}
      <div className="border border-border bg-card p-6">
        <h2 className="text-sm font-medium uppercase tracking-widest text-muted-foreground mb-4">
          Использование auth-proxy
        </h2>
        <p className="text-sm text-muted-foreground mb-3">
          Отправь POST-запрос с токеном в заголовке — прокси выполнит GET к целевому URL с кредами Lambda Runtime и запишет результат в лог.
        </p>
        <pre className="text-xs mono bg-background border border-border p-4 overflow-x-auto text-muted-foreground">
{`POST /auth-proxy
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{ "target_url": "https://your-service.example.com/api" }

→ { "status": 200 }`}
        </pre>
        <button
          onClick={() => onNavigate('monitoring')}
          className="mt-4 text-xs mono text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
        >
          Посмотреть логи <Icon name="ArrowRight" size={12} />
        </button>
      </div>
    </div>
  );
}
