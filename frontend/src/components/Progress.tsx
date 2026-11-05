import { useEffect, useState } from 'react';
import { Target } from 'lucide-react';

import { api, type Progress as ProgressData, type Script } from '../api';
import { button, card, ErrorBanner, label, Spinner } from '../ui';
import { LevelDot } from './Meter';

/** How it's going: how much of your part you know, your weakest lines, and
    the last fortnight's practice. */
export function Progress({ script, onDrill, onLine, changes }: {
  script: Script;
  onDrill: () => void;
  onLine: (element: number) => void;
  changes: number;
}) {
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.progress(script.id).then(setData).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [script.id, changes]);

  if (error) return <ErrorBanner>{error}</ErrorBanner>;
  if (!data) return <Spinner className="mx-auto mt-8 h-5 w-5 text-ink-500" />;

  const day = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 px-3 py-4">
      <section className={`${card} p-4`}>
        <p className="text-3xl font-semibold text-ink-50">{Math.round(data.mastery * 100)}%</p>
        <p className="text-sm text-ink-400">of your part known · {data.label}</p>
      </section>

      {data.weakest.length > 0 && (
        <section className="space-y-2">
          <h2 className={label}>Your weakest lines</h2>
          {data.weakest.map((line) => (
            <button key={line.id} type="button" onClick={() => onLine(line.id)}
              className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-ink-900">
              <span className="pt-1.5"><LevelDot level={line.level} attempts={line.attempts} /></span>
              <span className="text-sm text-ink-200">{line.text}</span>
            </button>
          ))}
          <button type="button" className={button} onClick={onDrill}>
            <Target className="h-4 w-4" /> Drill these
          </button>
        </section>
      )}

      <section className="space-y-1">
        <h2 className={label}>Practice</h2>
        {data.days.length === 0 && <p className="text-sm text-ink-500">Nothing yet in the last two weeks.</p>}
        {[...data.days].reverse().map((d) => (
          <p key={d.day} className="text-sm text-ink-300">
            <span className="text-ink-100">{day(d.day)}</span> · {d.attempts} lines · {Math.round(d.accuracy * 100)}% right
            {d.lines_called ? ` · called for ${d.lines_called}` : ''}
          </p>
        ))}
      </section>

      <section className="space-y-1">
        <h2 className={label}>Every line of yours</h2>
        {data.lines.map((line) => (
          <button key={line.id} type="button" onClick={() => onLine(line.id)}
            className="flex w-full items-start gap-2 rounded-md px-2 py-1 text-left hover:bg-ink-900">
            <span className="pt-1.5"><LevelDot level={line.level} attempts={line.attempts} /></span>
            <span className="min-w-0 flex-1 truncate text-sm text-ink-300">{line.text}</span>
          </button>
        ))}
      </section>
    </div>
  );
}
