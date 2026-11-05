// Serafina's controls, as her components spell them (pages/settings/shared.tsx,
// Sidebar, MediaLightbox), so Lines reads as part of her app. Touch
// screens get her 44px targets; desktop (md:) her denser sizes.

import { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

export const button =
  'inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-md border border-ink-700 px-3 text-sm ' +
  'text-ink-200 transition hover:bg-ink-800 disabled:pointer-events-none disabled:opacity-40 md:min-h-0 md:py-1.5';

export const primaryButton =
  'inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-md bg-accent-600 px-4 text-sm font-medium ' +
  'text-white transition hover:bg-accent-500 disabled:pointer-events-none disabled:opacity-40 md:min-h-0 md:py-1.5';

/** A destructive button: outlined in rose, solid once armed for its second tap. */
export function dangerButton(armed: boolean): string {
  return (
    'inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-md border px-3 text-sm transition ' +
    'disabled:pointer-events-none disabled:opacity-40 md:min-h-0 md:py-1.5 ' +
    (armed ? 'border-transparent bg-rose-600 text-white' : 'border-rose-900 text-rose-300 hover:bg-rose-950/60')
  );
}

export const iconButton =
  'flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-md text-ink-400 transition ' +
  'hover:bg-ink-800 hover:text-ink-100 disabled:opacity-40 md:min-h-0 md:min-w-0 md:p-1.5';

export const field =
  'w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 ' +
  'focus:border-accent-500 focus:outline-none disabled:opacity-50';

export const label = 'text-[11px] font-semibold uppercase tracking-wider text-ink-500';

export const card = 'rounded-md border border-ink-800 bg-ink-900';

/** Her round, frosted buttons over media (MediaLightbox). */
export const overlayButton =
  'flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-full bg-white/10 px-3 text-sm ' +
  'text-white backdrop-blur-sm transition hover:bg-white/20';

/** A toggle chip: her sidebar tabs and segmented control. */
export function Chip({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      title={title}
      onClick={onClick}
      className={
        'inline-flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition ' +
        'md:min-h-[32px] ' +
        (active ? 'bg-ink-800 text-ink-50' : 'text-ink-400 hover:bg-ink-800/60 hover:text-ink-100')
      }
    >
      {children}
    </button>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label: ariaLabel,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel}
      className="inline-flex shrink-0 gap-0.5 rounded-lg border border-ink-800 bg-ink-900/40 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={
            'inline-flex min-h-[38px] items-center rounded-md px-3 text-[13px] font-medium transition md:min-h-[28px] ' +
            (value === o.value ? 'bg-accent-500 text-white' : 'text-ink-400 hover:text-ink-100')
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-rose-900 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">{children}</div>
  );
}

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return <Loader2 className={`${className} animate-spin`} aria-hidden="true" />;
}

// this app's own: its own controls, in her look, to the end of the file
