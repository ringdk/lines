export const LEVELS: Record<number, string> = {
  1: 'Just starting',
  2: 'Getting familiar',
  3: 'Getting there',
  4: 'Nearly off book',
  5: 'Off book',
};

/** How well you know it: five steps of difficulty, lit to the level the
    suggestions are set at, and how much of the script you know. */
export function Meter({ level, mastery, pinned, done, total }: {
  level: number;
  mastery: number;
  pinned?: boolean;
  done?: number;
  total?: number;
}) {
  return (
    <div className="flex items-center gap-3" aria-label={`Level ${level} of 5, ${LEVELS[level]}. You know ${Math.round(mastery * 100)}%.`}>
      <div className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((step) => (
          <span
            key={step}
            className={`h-2 w-5 rounded-full transition-colors duration-500 ${step <= level ? (level >= 4 ? 'bg-accent-500' : 'bg-accent-600/80') : 'bg-ink-800'}`}
          />
        ))}
      </div>
      <div className="min-w-0 text-xs leading-tight">
        <span className="font-medium text-ink-200">{LEVELS[level]}</span>
        {pinned && <span className="text-ink-500"> · set by you</span>}
        <span className="block text-ink-500">
          Know {Math.round(mastery * 100)}%{total ? ` · line ${Math.min((done ?? 0) + 1, total)} of ${total}` : ''}
        </span>
      </div>
    </div>
  );
}

/** A line's level as a small dot, for lists. */
export function LevelDot({ level, attempts }: { level: number; attempts: number }) {
  const shade = attempts === 0 ? 'bg-ink-700' : level >= 4 ? 'bg-emerald-500' : level >= 3 ? 'bg-amber-400' : 'bg-rose-500';
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${shade}`} title={attempts ? LEVELS[level] : 'Not tried yet'} />;
}
