import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

import { iconButton } from '../ui';

/** A sheet from the bottom on a phone, a card in the middle from md: up.
    A tap outside or Escape closes it; its close button is on the left, clear
    of the corner iOS keeps for itself. */
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/60 md:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className="max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl border border-ink-800 bg-ink-950 pb-[max(env(safe-area-inset-bottom),1rem)] md:max-w-lg md:rounded-2xl md:pb-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center gap-2 border-b border-ink-800 bg-ink-950 px-2 py-2">
          <button type="button" className={iconButton} onClick={onClose} aria-label="Close">
            <X className="h-5 w-5 md:h-4 md:w-4" />
          </button>
          <h2 className="font-semibold text-ink-50">{title}</h2>
        </div>
        <div className="space-y-4 px-4 pt-4">{children}</div>
      </div>
    </div>
  );
}

/** A labelled on/off switch, the whole row a touch target. */
export function Toggle({ label, hint, on, onChange }: {
  label: string;
  hint?: string;
  on: boolean;
  onChange: (on: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className="flex min-h-[44px] w-full items-center justify-between gap-3 text-left"
    >
      <span>
        <span className="block text-sm text-ink-100">{label}</span>
        {hint && <span className="block text-xs text-ink-500">{hint}</span>}
      </span>
      <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${on ? 'bg-accent-600' : 'bg-ink-700'}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${on ? 'left-[22px]' : 'left-0.5'}`} />
      </span>
    </button>
  );
}
