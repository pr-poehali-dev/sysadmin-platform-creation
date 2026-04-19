import { useState } from 'react';
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import HomePage from './pages/HomePage';
import ServicesPage from './pages/ServicesPage';
import MonitoringPage from './pages/MonitoringPage';
import Icon from '@/components/ui/icon';

type Page = 'home' | 'services' | 'monitoring';

const nav: { id: Page; label: string; icon: string }[] = [
  { id: 'home',       label: 'Главная',    icon: 'LayoutDashboard' },
  { id: 'services',   label: 'Сервисы',    icon: 'Box' },
  { id: 'monitoring', label: 'Мониторинг', icon: 'Activity' },
];

export default function App() {
  const [page, setPage] = useState<Page>('home');

  return (
    <TooltipProvider>
      <Toaster />
      <div className="min-h-screen flex bg-background">
        {/* Sidebar */}
        <aside className="w-56 flex-shrink-0 border-r border-border flex flex-col">
          <div className="px-6 py-6 border-b border-border">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full dot-ok animate-pulse-dot" />
              <span className="font-semibold text-sm tracking-widest uppercase text-foreground/80 mono">
                MeshControl
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 mono">v1.0.0</p>
          </div>

          <nav className="flex-1 py-4">
            {nav.map((item) => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                className={`w-full flex items-center gap-3 px-6 py-3 text-sm transition-colors text-left
                  ${page === item.id
                    ? 'text-foreground border-r-2 border-primary bg-muted/40'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/20'
                  }`}
              >
                <Icon name={item.icon} size={15} />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="px-6 py-4 border-t border-border">
            <div className="text-xs text-muted-foreground mono">
              <div className="flex justify-between">
                <span>Функции</span>
                <span className="status-ok">2 активны</span>
              </div>
              <div className="flex justify-between mt-1">
                <span>БД</span>
                <span className="status-ok">online</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col min-w-0">
          <header className="h-14 border-b border-border flex items-center px-8 justify-between flex-shrink-0">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Icon name="ChevronRight" size={14} />
              <span className="text-foreground font-medium">
                {nav.find(n => n.id === page)?.label}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs mono text-muted-foreground">
              <span>{new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })}</span>
            </div>
          </header>

          <div className="flex-1 overflow-auto p-8 animate-fade-in" key={page}>
            {page === 'home'       && <HomePage onNavigate={setPage} />}
            {page === 'services'   && <ServicesPage />}
            {page === 'monitoring' && <MonitoringPage />}
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}
