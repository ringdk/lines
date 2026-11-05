import { useEffect, useState } from 'react';
import { Pencil, Play, Repeat } from 'lucide-react';

import { api, type Element, type Script } from '../api';
import { button, ErrorBanner } from '../ui';
import { LevelDot } from './Meter';
import { Sheet } from './Sheet';

/** The whole script: your lines marked with how well you know them. Tap any
    line to run from it, loop a stretch, or fix it. */
export function ScriptView({ script, onScript, onRehearse, onEdit, focus }: {
  script: Script;
  onScript: (s: Script) => void;
  onRehearse: () => void;
  onEdit: (element: number) => void;
  focus: number | null;
}) {
  const [picked, setPicked] = useState<Element | null>(null);
  const [loopStart, setLoopStart] = useState<number | null>(null);
  const [error, setError] = useState('');
  const mine = new Set(script.mine.map((m) => m.toLowerCase()));
  const loop = script.settings.loop;
  const index = new Map(script.elements.map((e, i) => [e.id, i]));
  const inLoop = (e: Element) =>
    loop !== null && (index.get(e.id) ?? -1) >= (index.get(loop.from) ?? 0) && (index.get(e.id) ?? -1) <= (index.get(loop.to) ?? -1);

  useEffect(() => {
    if (focus !== null) document.getElementById(`el-${focus}`)?.scrollIntoView({ block: 'center' });
  }, [focus]);

  const runFrom = async (e: Element) => {
    try {
      await api.jump(script.id, e.id);
      onRehearse();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const setLoop = async (from: number, to: number) => {
    try {
      const s = await api.update(script.id, { settings: { loop: { from, to } } });
      onScript(s);
      await api.jump(script.id, 'top');
      setLoopStart(null);
      onRehearse();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-2 px-3 py-4">
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {loopStart !== null && (
        <p className="rounded-md border border-accent-600 bg-accent-950/50 px-3 py-2 text-sm text-ink-100">
          Now tap the line to loop back from.
        </p>
      )}
      {script.elements.map((e) => {
        const yours = e.kind === 'line' && mine.has((e.character ?? '').toLowerCase());
        const state = script.lines[String(e.id)];
        const ring = e.id === focus || e.id === loopStart ? 'ring-1 ring-accent-500' : '';
        return (
          <button
            key={e.id}
            id={`el-${e.id}`}
            type="button"
            onClick={() => (loopStart !== null ? setLoop(loopStart, e.id) : setPicked(e))}
            className={`block w-full rounded-md px-2 py-1.5 text-left transition hover:bg-ink-900 ${inLoop(e) ? 'border-l-2 border-accent-600' : ''} ${ring}`}
          >
            {e.kind === 'heading' && <span className="text-xs font-semibold uppercase tracking-wider text-ink-400">{e.text}</span>}
            {e.kind === 'direction' && <span className="block px-4 text-sm italic text-ink-500">{e.text}</span>}
            {e.kind === 'line' && (
              <span className="flex gap-2">
                <span className="w-20 shrink-0 pt-0.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  {e.character}
                </span>
                <span className={`min-w-0 flex-1 text-[15px] leading-snug ${yours ? 'text-ink-50' : 'text-ink-300'}`}>
                  {e.note && <span className="italic text-ink-500">{e.note} </span>}
                  {e.text}
                </span>
                {yours && state && <span className="pt-1.5"><LevelDot level={state.level} attempts={state.attempts} /></span>}
              </span>
            )}
          </button>
        );
      })}

      {picked && (
        <Sheet title={picked.kind === 'line' ? `${picked.character}'s line` : 'Direction'} onClose={() => setPicked(null)}>
          <p className="text-sm text-ink-300">{picked.text}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={button} onClick={() => runFrom(picked)}>
              <Play className="h-4 w-4" /> Run from here
            </button>
            <button type="button" className={button} onClick={() => { setLoopStart(picked.id); setPicked(null); }}>
              <Repeat className="h-4 w-4" /> Loop from here
            </button>
            <button type="button" className={button} onClick={() => onEdit(picked.id)}>
              <Pencil className="h-4 w-4" /> Fix it
            </button>
          </div>
        </Sheet>
      )}
    </div>
  );
}
