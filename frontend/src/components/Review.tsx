import { useEffect, useState } from 'react';
import { Merge, Play, Plus, Scissors, Trash2 } from 'lucide-react';

import { api, type Element, type Script } from '../api';
import { useTwoTap } from '../twoTap';
import { button, Chip, dangerButton, ErrorBanner, field, label, primaryButton } from '../ui';

/** Check what was read: who you play, the characters' names, and any line
    that went to the wrong person or should be a direction. */
export function Review({ script, onScript, onRehearse, focus }: {
  script: Script;
  onScript: (s: Script) => void;
  onRehearse: () => void;
  focus: number | null;
}) {
  const [error, setError] = useState('');
  const [open, setOpen] = useState<number | null>(focus);

  useEffect(() => {
    if (focus !== null) document.getElementById(`edit-${focus}`)?.scrollIntoView({ block: 'center' });
  }, [focus]);

  const run = async (work: () => Promise<Script>) => {
    try {
      onScript(await work());
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const toggleMine = (name: string) => {
    const mine = script.mine.includes(name) ? script.mine.filter((m) => m !== name) : [...script.mine, name];
    void run(() => api.update(script.id, { mine }));
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 px-3 py-4">
      {error && <ErrorBanner>{error}</ErrorBanner>}

      <section className="space-y-2">
        <h2 className={label}>Who do you play?</h2>
        <div className="flex flex-wrap gap-1.5">
          {script.characters.map((name) => (
            <Chip key={name} active={script.mine.includes(name)} onClick={() => toggleMine(name)}>
              {name}
            </Chip>
          ))}
        </div>
        <button type="button" className={primaryButton} disabled={script.mine.length === 0} onClick={onRehearse}>
          <Play className="h-4 w-4" /> Looks right — rehearse
        </button>
      </section>

      <section className="space-y-2">
        <h2 className={label}>Names</h2>
        <p className="text-xs text-ink-500">Rename one to fold it into another (say "DAVID" into "David").</p>
        {script.characters.map((name) => (
          <Rename key={name} name={name} onRename={(to) => run(() => api.rename(script.id, name, to))} />
        ))}
      </section>

      <section className="space-y-1">
        <h2 className={label}>The script, as read</h2>
        <p className="text-xs text-ink-500">Tap anything that came out wrong.</p>
        {script.elements.map((e) => (
          <ElementRow
            key={e.id}
            element={e}
            characters={script.characters}
            open={open === e.id}
            onOpen={() => setOpen(open === e.id ? null : e.id)}
            onChange={(change) => run(() => api.element(script.id, e.id, change))}
          />
        ))}
      </section>
    </div>
  );
}

function Rename({ name, onRename }: { name: string; onRename: (to: string) => void }) {
  const [value, setValue] = useState(name);
  useEffect(() => setValue(name), [name]);
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim() && value.trim() !== name) onRename(value.trim());
      }}
    >
      <input className={field} value={value} onChange={(e) => setValue(e.target.value)} aria-label={`Rename ${name}`} maxLength={40} />
      <button type="submit" className={button} disabled={!value.trim() || value.trim() === name}>
        Rename
      </button>
    </form>
  );
}

function ElementRow({ element: e, characters, open, onOpen, onChange }: {
  element: Element;
  characters: string[];
  open: boolean;
  onOpen: () => void;
  onChange: (change: Record<string, unknown>) => void;
}) {
  const [kind, setKind] = useState(e.kind);
  const [who, setWho] = useState(e.character ?? characters[0] ?? '');
  const [text, setText] = useState(e.text);
  const [cursor, setCursor] = useState<number | null>(null);
  const { armed, tap } = useTwoTap();

  useEffect(() => {
    setKind(e.kind);
    setWho(e.character ?? characters[0] ?? '');
    setText(e.text);
  }, [e, characters]);

  const dirty = kind !== e.kind || text !== e.text || (kind === 'line' && who !== e.character);

  if (!open) {
    return (
      <button id={`edit-${e.id}`} type="button" onClick={onOpen} className="block w-full rounded-md px-2 py-1.5 text-left hover:bg-ink-900">
        {e.kind === 'line' ? (
          <span className="flex gap-2">
            <span className="w-20 shrink-0 pt-0.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{e.character}</span>
            <span className="min-w-0 flex-1 text-sm text-ink-200">
              {e.note && <span className="italic text-ink-500">{e.note} </span>}
              {e.text}
            </span>
          </span>
        ) : (
          <span className={`block text-sm ${e.kind === 'heading' ? 'font-semibold uppercase text-ink-400' : 'px-4 italic text-ink-500'}`}>
            {e.text}
          </span>
        )}
      </button>
    );
  }

  return (
    <div id={`edit-${e.id}`} className="space-y-2 rounded-md border border-accent-600 bg-ink-900 p-3">
      <div className="flex flex-wrap gap-2">
        <select className={`${field} w-auto`} value={kind} onChange={(ev) => setKind(ev.target.value as Element['kind'])} aria-label="What it is">
          <option value="line">A line</option>
          <option value="direction">A direction</option>
          <option value="heading">A heading</option>
        </select>
        {kind === 'line' && (
          <select className={`${field} w-auto`} value={who} onChange={(ev) => setWho(ev.target.value)} aria-label="Who says it">
            {characters.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>
      <textarea
        className={`${field} min-h-[88px]`}
        value={text}
        onChange={(ev) => setText(ev.target.value)}
        onSelect={(ev) => setCursor(ev.currentTarget.selectionStart)}
        aria-label="Its words"
      />
      <div className="flex flex-wrap gap-2">
        <button type="button" className={primaryButton} disabled={!dirty || !text.trim()}
          onClick={() => onChange({ action: 'edit', kind, character: kind === 'line' ? who : null, text })}>
          Save
        </button>
        <button type="button" className={button} disabled={dirty || cursor === null || cursor <= 0 || cursor >= e.text.length}
          onClick={() => cursor !== null && onChange({ action: 'split', at: cursor })} title="Split where the cursor is">
          <Scissors className="h-4 w-4" /> Split here
        </button>
        <button type="button" className={button} onClick={() => onChange({ action: 'merge' })} title="Join with the next">
          <Merge className="h-4 w-4" /> Join next
        </button>
        <button type="button" className={button}
          onClick={() => onChange({ action: 'insert', kind: 'direction', text: 'A beat.' })} title="Add a direction after it">
          <Plus className="h-4 w-4" /> Add after
        </button>
        <button type="button" className={dangerButton(armed)} onClick={() => tap(() => onChange({ action: 'delete' }))}>
          <Trash2 className="h-4 w-4" /> {armed ? 'Delete?' : ''}
        </button>
      </div>
    </div>
  );
}
