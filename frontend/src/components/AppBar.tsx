import { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';

import { iconButton } from '../ui';

/** Serafina's header bar, as every app's pages have it: back to her (or up a level), her mark, the title. */
export function AppBar({ title, onBack, children }: { title: string; onBack?: () => void; children?: ReactNode }) {
  return (
    <header className="flex items-center gap-2 border-b border-ink-800 px-3 pb-3 pt-[max(env(safe-area-inset-top),0.75rem)]">
      {onBack ? (
        <button type="button" onClick={onBack} className={iconButton} aria-label="Back">
          <ArrowLeft className="h-5 w-5 md:h-4 md:w-4" />
        </button>
      ) : (
        <a href="/" target="_top" className={iconButton} aria-label="Back to Serafina">
          <ArrowLeft className="h-5 w-5 md:h-4 md:w-4" />
        </a>
      )}
      <div className="flex min-w-0 items-center gap-2 font-semibold text-ink-50">
        <img src="/icon-192.png" alt="" className="h-5 w-5 shrink-0 rounded"
          onError={(e) => { e.currentTarget.hidden = true; }} />
        <span className="truncate">{title}</span>
      </div>
      {children && <div className="ml-auto flex shrink-0 items-center gap-1">{children}</div>}
    </header>
  );
}
