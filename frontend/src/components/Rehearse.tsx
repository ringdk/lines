import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, Repeat, RotateCcw, SendHorizontal, SlidersHorizontal, Target, Undo2, Users } from 'lucide-react';

import { api, ApiError, type Element, type Graded, type RunView, type Script, type Settings } from '../api';
import { showOnScreen } from '../serafina';
import { chipsFor, wordCount } from '../suggest';
import { button, ErrorBanner, field, iconButton, label, primaryButton, Segmented, Spinner } from '../ui';
import { LEVELS, Meter } from './Meter';
import { Sheet, Toggle } from './Sheet';

type Item =
  | { key: string; type: 'cue'; el: Element; past?: boolean }
  | { key: string; type: 'loop' }
  | { key: string; type: 'you'; text: string; perfect: boolean }
  | { key: string; type: 'line'; graded: Graded }
  | { key: string; type: 'level'; from: number; to: number };

let counter = 0;
const key = () => String(++counter);

function cueItems(view: RunView, past = false): Item[] {
  const items: Item[] = [];
  for (const el of view.context) items.push({ key: key(), type: 'cue', el, past: true });
  for (const cue of view.cues) {
    if (cue.kind === 'loop') items.push({ key: key(), type: 'loop' });
    else items.push({ key: key(), type: 'cue', el: cue as Element, past });
  }
  return items;
}

/** The last few words of a cue: what you'd actually hear before coming in. */
function tailOf(text: string, words = 6): string {
  const parts = text.split(/\s+/);
  return parts.length <= words ? text : `…${parts.slice(-words).join(' ')}`;
}

export function Rehearse({ script, onScript, onReview, changes }: {
  script: Script;
  onScript: (s: Script) => void;
  onReview: () => void;
  changes: number;
}) {
  const [view, setView] = useState<RunView | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [text, setText] = useState('');
  const [helped, setHelped] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wrongChip, setWrongChip] = useState<number | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const input = useRef<HTMLTextAreaElement | null>(null);

  const fresh = useCallback(async () => {
    try {
      const v = await api.run(script.id);
      setView(v);
      setItems(cueItems(v));
      setText('');
      setHelped(0);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [script.id]);

  useEffect(() => {
    void fresh();
  }, [fresh, changes]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [items, view?.prompt?.id]);

  const prompt = view?.prompt ?? null;
  const settings = view?.settings ?? script.settings;
  const level = prompt?.level ?? 1;

  useEffect(() => {
    if (!view) return;
    showOnScreen({
      label: `${script.title}${prompt ? ` · your line ${Math.min((view.done ?? 0) + 1, view.total)} of ${view.total}` : ''}`,
      items: [{ kind: 'script', id: String(script.id) }, ...(prompt ? [{ kind: 'line', id: String(prompt.id) }] : [])],
    });
  }, [view, prompt, script.id, script.title]);

  const chips = useMemo(
    () => (prompt && settings.suggestions && settings.input === 'words' ? chipsFor(prompt, text, level) : null),
    [prompt, settings.suggestions, settings.input, text, level],
  );

  const act = async (work: () => Promise<RunView>) => {
    setBusy(true);
    try {
      const v = await work();
      setView(v);
      setItems((old) => [...old, ...cueItems({ ...v, context: [] })]);
      setText('');
      setHelped(0);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const jump = (to: 'top' | 'back') => {
    setBusy(true);
    api
      .jump(script.id, to)
      .then((v) => {
        setView(v);
        setItems(cueItems(v));
        setText('');
        setHelped(0);
        setError('');
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  const send = async (gaveUp: boolean) => {
    if (!prompt || busy) return;
    if (!gaveUp && !text.trim()) return;
    setBusy(true);
    const typed = text;
    try {
      const out = await api.attempt(script.id, {
        line_id: prompt.id,
        text: typed,
        mode: settings.input,
        helped,
        gave_up: gaveUp,
      });
      const perfect = out.graded.words.every((w) => w.status === 'ok') && out.graded.extra.length === 0;
      const said = typed.trim() || 'Line!';
      const next: Item[] = [{ key: key(), type: 'you', text: gaveUp && typed.trim() ? `${said} … Line!` : said, perfect }];
      if (!perfect) next.push({ key: key(), type: 'line', graded: out.graded });
      if (settings.level === 'auto' && out.line.level !== prompt.level) {
        next.push({ key: key(), type: 'level', from: prompt.level, to: out.line.level });
      }
      setItems((old) => [...old, ...next, ...cueItems({ ...out.view, context: [] })]);
      setView(out.view);
      setText('');
      setHelped(0);
      setError('');
      input.current?.focus();
    } catch (e) {
      if (e instanceof ApiError && /up next/.test(e.message)) {
        await fresh();
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void send(false);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(false);
    }
  };

  const pick = (i: number) => {
    if (!chips) return;
    const chosen = chips.options[i];
    if (i !== chips.right) {
      setWrongChip(i);
      window.setTimeout(() => setWrongChip(null), 450);
    }
    setText((t) => `${t.trim() ? `${t.trimEnd()} ` : ''}${chosen} `);
    setHelped((h) => h + wordCount(chosen));
    input.current?.focus();
  };

  const change = async (patch: Partial<Settings>) => {
    try {
      const s = await api.update(script.id, { settings: patch });
      onScript(s);
      setView((v) => (v ? { ...v, settings: s.settings } : v));
      if ('level' in patch || 'loop' in patch) await fresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (!view) {
    return error ? <ErrorBanner>{error}</ErrorBanner> : <Spinner className="mx-auto mt-8 h-5 w-5 text-ink-500" />;
  }

  if (view.needs_character) {
    return (
      <div className="space-y-3 px-3 py-6 text-center">
        <Users className="mx-auto h-8 w-8 text-ink-500" />
        <p className="text-sm text-ink-300">Who do you play? Pick your part and I'll read the others.</p>
        <button type="button" className={primaryButton} onClick={onReview}>
          Choose your character
        </button>
      </div>
    );
  }

  const hidden = (el: Element) => el.kind === 'direction' && !settings.directions;
  const mine = new Set(view.mine.map((m) => m.toLowerCase()));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-ink-800 px-3 py-2">
        <Meter level={level} mastery={view.mastery} pinned={settings.level !== 'auto'} done={view.done} total={view.total} />
        {settings.loop && (
          <span className="inline-flex items-center gap-1 text-xs text-ink-400">
            <Repeat className="h-3.5 w-3.5" /> Looping
          </span>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-4" aria-live="polite">
        {items.map((item) => {
          if (item.type === 'cue') {
            if (hidden(item.el)) return null;
            if (item.el.kind === 'line' && mine.has((item.el.character ?? '').toLowerCase())) {
              return <YouRow key={item.key} text={item.el.text} perfect={false} past />;
            }
            return <CueRow key={item.key} el={item.el} past={item.past} cueView={settings.cue_view} />;
          }
          if (item.type === 'loop') {
            return (
              <p key={item.key} className="flex items-center justify-center gap-1.5 text-xs text-ink-500">
                <Repeat className="h-3.5 w-3.5" /> Round again
              </p>
            );
          }
          if (item.type === 'you') return <YouRow key={item.key} text={item.text} perfect={item.perfect} />;
          if (item.type === 'level') {
            return (
              <p key={item.key} className="text-center text-xs text-ink-400">
                {item.to > item.from ? '↑' : '↓'} {LEVELS[item.to]} on that line
              </p>
            );
          }
          return <LineRow key={item.key} graded={item.graded} />;
        })}

        {view.end && (
          <div className="space-y-3 rounded-lg border border-ink-800 bg-ink-900 p-4 text-center">
            <p className="text-sm text-ink-200">That's the end of the scene.</p>
            <div className="flex flex-wrap justify-center gap-2">
              <button type="button" className={button} onClick={() => jump('top')} disabled={busy}>
                <RotateCcw className="h-4 w-4" /> From the top
              </button>
              <button type="button" className={button} onClick={() => act(() => api.drill(script.id))} disabled={busy}>
                <Target className="h-4 w-4" /> Drill my weakest
              </button>
            </div>
          </div>
        )}
        <div ref={bottom} />
      </div>

      {view.mode === 'drill' && (
        <div className="flex items-center justify-between gap-2 border-t border-ink-800 bg-ink-900 px-3 py-1.5 text-xs text-ink-300">
          <span>
            <Target className="mr-1 inline h-3.5 w-3.5" />
            Drilling your weakest lines · {view.remaining ?? 0} to go
          </span>
          <button type="button" className={button} onClick={() => act(() => api.stopDrill(script.id))} disabled={busy}>
            Stop
          </button>
        </div>
      )}

      <form onSubmit={submit} className="space-y-2 border-t border-ink-800 bg-ink-950 px-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] pt-2">
        {error && <ErrorBanner>{error}</ErrorBanner>}
        <div className="flex items-center gap-1">
          <button type="button" className={iconButton} onClick={() => jump('top')} disabled={busy} aria-label="Back to the top" title="Back to the top">
            <RotateCcw className="h-5 w-5 md:h-4 md:w-4" />
          </button>
          <button type="button" className={iconButton} onClick={() => jump('back')} disabled={busy} aria-label="Back one exchange" title="Back one exchange">
            <Undo2 className="h-5 w-5 md:h-4 md:w-4" />
          </button>
          <button type="button" className={iconButton} onClick={() => act(() => api.drill(script.id))} disabled={busy} aria-label="Drill my weakest lines" title="Drill my weakest lines">
            <Target className="h-5 w-5 md:h-4 md:w-4" />
          </button>
          <button type="button" className={iconButton} onClick={() => setSettingsOpen(true)} aria-label="How it runs" title="How it runs">
            <SlidersHorizontal className="h-5 w-5 md:h-4 md:w-4" />
          </button>
          {prompt && (
            <span className="ml-auto truncate text-xs text-ink-500">
              {prompt.character}
              {prompt.note ? ` ${prompt.note}` : ''} · {prompt.words.length} words
            </span>
          )}
        </div>

        {chips && (
          <div className="flex flex-wrap gap-2" aria-label="Suggestions">
            {chips.options.map((option, i) => (
              <button
                key={`${chips.at}-${option}`}
                type="button"
                onClick={() => pick(i)}
                className={`min-h-[44px] rounded-full border px-3 text-sm transition md:min-h-[32px] ${wrongChip === i ? 'border-rose-500 bg-rose-950/60 text-rose-200' : 'border-ink-700 bg-ink-900 text-ink-100 hover:border-accent-500'}`}
              >
                {option}
              </button>
            ))}
          </div>
        )}

        {/* The bottom-left corner is Serafina's: her Ask button sits there. */}
        <div className="flex items-end gap-2 pl-16 md:pl-0">
          <textarea
            ref={input}
            className={`${field} max-h-32 min-h-[44px] resize-none`}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            placeholder={!prompt ? '' : settings.input === 'letters' ? 'First letters…' : 'Your line…'}
            aria-label="Your line"
            enterKeyHint="send"
            autoCapitalize="sentences"
            autoCorrect="off"
            spellCheck={false}
            disabled={!prompt || busy}
          />
          <button type="button" className={button} onClick={() => send(true)} disabled={!prompt || busy} title="Show me the line">
            Line!
          </button>
          <button type="submit" className={primaryButton} disabled={!prompt || busy || !text.trim()} aria-label="Say it">
            {busy ? <Spinner /> : <SendHorizontal className="h-4 w-4" />}
          </button>
        </div>
      </form>

      {settingsOpen && (
        <Sheet title="How it runs" onClose={() => setSettingsOpen(false)}>
          <Toggle label="Suggestions" hint="Words to tap when you're stuck" on={settings.suggestions} onChange={(on) => change({ suggestions: on })} />
          <Toggle label="Cue view" hint="Only the end of each cue, as you'd hear it" on={settings.cue_view} onChange={(on) => change({ cue_view: on })} />
          <Toggle label="Stage directions" on={settings.directions} onChange={(on) => change({ directions: on })} />
          <div className="space-y-1.5">
            <p className={label}>Your line as</p>
            <Segmented
              label="Input"
              value={settings.input}
              options={[{ value: 'words', label: 'Words' }, { value: 'letters', label: 'First letters' }]}
              onChange={(v) => change({ input: v })}
            />
          </div>
          <div className="space-y-1.5">
            <p className={label}>Difficulty</p>
            <Segmented
              label="Difficulty"
              value={String(settings.level)}
              options={[{ value: 'auto', label: 'Auto' }, ...[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: String(n) }))]}
              onChange={(v) => change({ level: v === 'auto' ? 'auto' : (Number(v) as 1 | 2 | 3 | 4 | 5) })}
            />
            <p className="text-xs text-ink-500">Auto follows how well you know each line.</p>
          </div>
          {settings.loop && (
            <button type="button" className={button} onClick={() => change({ loop: null })}>
              <Repeat className="h-4 w-4" /> Stop looping
            </button>
          )}
        </Sheet>
      )}
    </div>
  );
}

function CueRow({ el, past, cueView }: { el: Element; past?: boolean; cueView: boolean }) {
  const [open, setOpen] = useState(false);
  if (el.kind === 'heading') {
    return <p className={`text-center text-xs font-semibold uppercase tracking-wider text-ink-500 ${past ? 'opacity-50' : ''}`}>{el.text}</p>;
  }
  if (el.kind === 'direction') {
    return <p className={`px-6 text-center text-sm italic text-ink-400 ${past ? 'opacity-50' : ''}`}>{el.text}</p>;
  }
  const short = cueView && !open && !past ? tailOf(el.text) : el.text;
  return (
    <div className={`max-w-[85%] ${past ? 'opacity-50' : ''}`}>
      <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-accent-300">{el.character}</p>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="block rounded-2xl rounded-tl-sm bg-ink-800 px-3 py-2 text-left text-[15px] leading-snug text-ink-100"
        disabled={!cueView || past}
      >
        {el.note && <span className="italic text-ink-400">{el.note} </span>}
        {short}
      </button>
      {el.interrupted && !past && <p className="mt-0.5 text-xs text-amber-300">Cut off — come straight in</p>}
    </div>
  );
}

function YouRow({ text, perfect, past }: { text: string; perfect: boolean; past?: boolean }) {
  return (
    <div className={`ml-auto flex max-w-[85%] items-end justify-end gap-1.5 ${past ? 'opacity-50' : ''}`}>
      {perfect && <Check className="mb-2 h-4 w-4 shrink-0 text-emerald-400" aria-label="Word perfect" />}
      <p className="rounded-2xl rounded-br-sm bg-accent-950 px-3 py-2 text-[15px] leading-snug text-ink-50">{text}</p>
    </div>
  );
}

const STYLE: Record<string, string> = {
  ok: 'text-ink-100',
  minor: 'font-bold text-amber-300',
  wrong: 'font-bold text-rose-300',
  missed: 'text-ink-300',
};

/** Your line as written: what you got wrong in bold, near misses in amber,
    the rest of it after where you stopped. */
function LineRow({ graded }: { graded: Graded }) {
  const reached = graded.words.findIndex((w) => w.status === 'missed');
  const stopped = reached === -1 ? graded.words.length : reached;
  const wrong = graded.words.filter((w) => w.status === 'wrong').length;
  const minor = graded.words.filter((w) => w.status === 'minor').length;
  return (
    <div className="max-w-[85%]">
      <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        Your line{stopped < graded.words.length ? (stopped === 0 ? '' : ' — the rest') : ''}
      </p>
      <p className="rounded-2xl rounded-tl-sm border border-ink-700 bg-ink-900 px-3 py-2 text-[15px] leading-snug">
        {graded.note && <span className="italic text-ink-500">{graded.note} </span>}
        {graded.words.map((w, i) => (
          <span key={i}>
            {w.lead}
            {i === stopped && stopped > 0 && <span className="text-ink-600">▸ </span>}
            <span className={STYLE[w.status]}>{w.text}</span>
          </span>
        ))}
        {graded.tail}
      </p>
      {(wrong > 0 || minor > 0 || graded.extra.length > 0) && (
        <p className="mt-0.5 text-xs text-ink-500">
          {[wrong && `${wrong} wrong (bold)`, minor && `${minor} close (amber)`,
            graded.extra.length && `you added "${graded.extra.map((x) => x.text).join(' ')}"`]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}
    </div>
  );
}

