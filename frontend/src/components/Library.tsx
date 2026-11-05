import { FormEvent, useEffect, useState } from 'react';
import { ChevronRight, ClipboardPaste, FileUp, Link, Plus, Trash2 } from 'lucide-react';

import { api, type Script, type ScriptSummary } from '../api';
import { useTwoTap } from '../twoTap';
import { card, dangerButton, ErrorBanner, field, label, primaryButton, Segmented, Spinner } from '../ui';
import { LEVELS } from './Meter';
import { Sheet } from './Sheet';

/** Your scripts, and a way to add one. */
export function Library({ onOpen, onAdded, changes }: {
  onOpen: (id: number) => void;
  onAdded: (s: Script) => void;
  changes: number;
}) {
  const [scripts, setScripts] = useState<ScriptSummary[] | null>(null);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);

  const load = () =>
    api
      .scripts()
      .then((s) => {
        setScripts(s);
        setError('');
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  useEffect(() => {
    void load();
  }, [changes]);

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 space-y-4 px-3 py-4">
      <button type="button" className={primaryButton} onClick={() => setAdding(true)}>
        <Plus className="h-4 w-4" /> Add a script
      </button>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {scripts === null && !error && <Spinner className="mx-auto h-5 w-5 text-ink-500" />}
      {scripts?.length === 0 && (
        <p className="text-sm text-ink-400">
          No scripts yet. Add one from a PDF, pasted text or a Google Doc, pick who you play, and I'll read the other parts.
        </p>
      )}
      <ul className="space-y-2">
        {scripts?.map((s) => <Row key={s.id} script={s} onOpen={() => onOpen(s.id)} onGone={load} onError={setError} />)}
      </ul>
      {adding && <AddSheet onClose={() => setAdding(false)} onAdded={onAdded} />}
    </main>
  );
}

function Row({ script: s, onOpen, onGone, onError }: {
  script: ScriptSummary;
  onOpen: () => void;
  onGone: () => void;
  onError: (message: string) => void;
}) {
  const { armed, tap } = useTwoTap();
  const level = s.mastery >= 0.85 ? 5 : s.mastery >= 0.7 ? 4 : s.mastery >= 0.5 ? 3 : s.mastery >= 0.3 ? 2 : 1;
  return (
    <li className={`${card} flex items-center gap-2 p-2`}>
      <button type="button" onClick={onOpen} className="flex min-h-[44px] min-w-0 flex-1 items-center gap-3 rounded px-2 text-left">
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium text-ink-50">{s.title}</span>
          <span className="block truncate text-xs text-ink-500">
            {s.mine.length ? `You play ${s.mine.join(' & ')}` : 'Pick who you play'} · {Math.round(s.mastery * 100)}% · {LEVELS[level]}
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-ink-500" />
      </button>
      <button
        type="button"
        className={dangerButton(armed)}
        aria-label={`Delete ${s.title}`}
        onClick={() =>
          tap(() =>
            api
              .remove(s.id)
              .then(onGone)
              .catch((e) => onError(e instanceof Error ? e.message : String(e))),
          )
        }
      >
        <Trash2 className="h-4 w-4" /> {armed ? 'Delete?' : ''}
      </button>
    </li>
  );
}

type Source = 'pdf' | 'text' | 'gdoc';

function AddSheet({ onClose, onAdded }: { onClose: () => void; onAdded: (s: Script) => void }) {
  const [source, setSource] = useState<Source>('pdf');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const ready = source === 'pdf' ? file !== null : source === 'text' ? text.trim().length > 0 : url.trim().length > 0;

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    try {
      const name = title.trim() || (file ? file.name.replace(/\.pdf$/i, '') : '');
      const s =
        source === 'pdf' && file
          ? await api.fromPdf(name, file)
          : source === 'text'
            ? await api.fromText(name, text)
            : await api.fromGoogleDoc(name, url.trim());
      onAdded(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title="Add a script" onClose={onClose}>
      <form onSubmit={add} className="space-y-4">
        <Segmented
          label="From"
          value={source}
          options={[
            { value: 'pdf', label: 'PDF' },
            { value: 'text', label: 'Paste' },
            { value: 'gdoc', label: 'Google Doc' },
          ]}
          onChange={setSource}
        />
        <div className="space-y-1.5">
          <label className={label} htmlFor="title">Title</label>
          <input id="title" className={field} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120}
            placeholder={source === 'pdf' && file ? file.name.replace(/\.pdf$/i, '') : 'The scene'} />
        </div>
        {source === 'pdf' && (
          <label className="flex min-h-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-ink-700 text-sm text-ink-300">
            <FileUp className="h-5 w-5" />
            {file ? file.name : 'Choose a PDF'}
            <input type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
        )}
        {source === 'text' && (
          <div className="space-y-1.5">
            <label className={label} htmlFor="text"><ClipboardPaste className="mr-1 inline h-3.5 w-3.5" />The script</label>
            <textarea id="text" className={`${field} min-h-[160px]`} value={text} onChange={(e) => setText(e.target.value)}
              placeholder={'DAVID: Lookit, I’m sorry for rushing over…\nEAVANNA: I’ll just call him.'} />
            <p className="text-xs text-ink-500">"Name: line" works best. Put stage directions in brackets.</p>
          </div>
        )}
        {source === 'gdoc' && (
          <div className="space-y-1.5">
            <label className={label} htmlFor="url"><Link className="mr-1 inline h-3.5 w-3.5" />Link to the doc</label>
            <input id="url" className={field} value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url"
              placeholder="https://docs.google.com/document/d/…" />
            <p className="text-xs text-ink-500">Share it with "Anyone with the link" first (Share → General access).</p>
          </div>
        )}
        {error && <ErrorBanner>{error}</ErrorBanner>}
        <button type="submit" className={primaryButton} disabled={!ready || busy}>
          {busy ? <Spinner /> : <Plus className="h-4 w-4" />} Add it
        </button>
      </form>
    </Sheet>
  );
}
