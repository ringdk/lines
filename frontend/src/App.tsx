import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { MessageCircle, Plus, Trash2 } from 'lucide-react';

import { api, Note } from './api';
import { AppBar } from './components/AppBar';
import { askAbout, showOnScreen, useSerafinaRequests, type Screen } from './serafina';
import { useTwoTap } from './twoTap';
import { button, card, dangerButton, ErrorBanner, field, primaryButton, Spinner } from './ui';

// The sample's page: your notes, a box to add one, and the two-way bridge to
// Serafina's page around it. Replace it with the app's own; keep the pieces
// it shows: text only from data (React children, never innerHTML), her
// controls from ui.tsx, nothing tappable top-right, and what's on screen
// offered to her panel.

function noteFrom(search: string): number | null {
  const value = new URLSearchParams(search).get('note');
  return value && /^\d+$/.test(value) ? Number(value) : null;
}

export default function App() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState('');
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [focus, setFocus] = useState<number | null>(() => noteFrom(window.location.search));

  const load = useCallback(async () => {
    try {
      setNotes(await api.notes());
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Her page asks for a view of this page, or says something changed.
  useSerafinaRequests({
    open: (search) => {
      window.history.replaceState(null, '', search || window.location.pathname);
      setFocus(noteFrom(search));
    },
    changed: () => void load(),
  });

  const screen = useMemo<Screen>(
    () => ({
      label: focus !== null ? `Note ${focus}` : 'Your notes',
      items: (notes ?? []).slice(0, 50).map((n) => ({ kind: 'note', id: String(n.id) })),
    }),
    [notes, focus],
  );

  useEffect(() => {
    if (notes) showOnScreen(screen);
  }, [notes, screen]);

  useEffect(() => {
    if (focus !== null) document.getElementById(`note-${focus}`)?.scrollIntoView({ block: 'center' });
  }, [focus, notes]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      await api.add(text);
      setText('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-[100dvh] flex-col pb-[env(safe-area-inset-bottom)]">
      <AppBar title="Lines" />
      <main className="mx-auto w-full max-w-2xl flex-1 space-y-4 px-3 py-4">
        <form onSubmit={add} className="flex gap-2">
          <input
            className={field}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Write something down"
            aria-label="New note"
            maxLength={2000}
          />
          <button type="submit" className={primaryButton} disabled={saving || !text.trim()}>
            {saving ? <Spinner /> : <Plus className="h-4 w-4" />} Add
          </button>
        </form>

        {error && <ErrorBanner>{error}</ErrorBanner>}
        {notes === null && !error && <Spinner className="mx-auto h-5 w-5 text-ink-500" />}
        {notes?.length === 0 && <p className="text-sm text-ink-500">No notes yet.</p>}

        <ul className="space-y-2">
          {notes?.map((n) => (
            <NoteRow key={n.id} note={n} focused={n.id === focus} onGone={load} onError={setError} />
          ))}
        </ul>

        {notes && notes.length > 0 && (
          <button type="button" className={button} onClick={() => askAbout(screen)}>
            <MessageCircle className="h-4 w-4" /> Ask Serafina about these
          </button>
        )}
      </main>
    </div>
  );
}

function NoteRow({ note, focused, onGone, onError }: {
  note: Note;
  focused: boolean;
  onGone: () => void;
  onError: (message: string) => void;
}) {
  const { armed, tap } = useTwoTap();
  const remove = () =>
    tap(async () => {
      try {
        await api.remove(note.id);
        onGone();
      } catch (e) {
        onError(e instanceof Error ? e.message : String(e));
      }
    });

  return (
    <li id={`note-${note.id}`} className={`${card} flex items-start gap-3 p-3 ${focused ? 'border-accent-600' : ''}`}>
      <div className="min-w-0 flex-1">
        <p className="whitespace-pre-wrap break-words text-sm text-ink-100">{note.body}</p>
        <p className="mt-1 text-xs text-ink-500">{new Date(note.created_at).toLocaleString()}</p>
      </div>
      <button type="button" className={dangerButton(armed)} onClick={remove} aria-label="Delete note">
        <Trash2 className="h-4 w-4" /> {armed ? 'Delete?' : ''}
      </button>
    </li>
  );
}
