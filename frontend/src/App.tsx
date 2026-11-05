import { useCallback, useEffect, useState } from 'react';
import { MessageCircle } from 'lucide-react';

import { api, type Script } from './api';
import { AppBar } from './components/AppBar';
import { Library } from './components/Library';
import { Progress } from './components/Progress';
import { Rehearse } from './components/Rehearse';
import { Review } from './components/Review';
import { ScriptView } from './components/ScriptView';
import { askAbout, showOnScreen, useSerafinaRequests } from './serafina';
import { ErrorBanner, iconButton, Segmented, Spinner } from './ui';

// Lines' pages: your scripts, and for each one rehearse, the script, your
// progress and the review of what was read. Where you are lives in the
// address (?script=3&view=rehearse), so back works and Serafina can show a
// page. Text only from data (React children, never innerHTML), her controls
// from ui.tsx, nothing tappable top-right, the bottom-left left for her.

type View = 'rehearse' | 'script' | 'progress' | 'review';
const VIEWS: View[] = ['rehearse', 'script', 'progress', 'review'];

interface Place {
  script: number | null;
  view: View;
  focus: number | null;
}

function placeFrom(search: string): Place {
  const q = new URLSearchParams(search);
  const id = q.get('script');
  const view = q.get('view') as View | null;
  const focus = q.get('line');
  return {
    script: id && /^\d+$/.test(id) ? Number(id) : null,
    view: view && VIEWS.includes(view) ? view : 'rehearse',
    focus: focus && /^\d+$/.test(focus) ? Number(focus) : null,
  };
}

function searchOf(place: Place): string {
  if (place.script === null) return window.location.pathname;
  const q = new URLSearchParams({ script: String(place.script), view: place.view });
  if (place.focus !== null) q.set('line', String(place.focus));
  return `?${q}`;
}

export default function App() {
  const [place, setPlace] = useState<Place>(() => placeFrom(window.location.search));
  const [script, setScript] = useState<Script | null>(null);
  const [error, setError] = useState('');
  const [changes, setChanges] = useState(0);

  const go = useCallback((next: Place, replace = false) => {
    const url = searchOf(next);
    if (replace) window.history.replaceState(null, '', url);
    else window.history.pushState(null, '', url);
    setPlace(next);
  }, []);

  useEffect(() => {
    const onPop = () => setPlace(placeFrom(window.location.search));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (place.script === null) {
      setScript(null);
      return;
    }
    api
      .script(place.script)
      .then((s) => {
        setScript(s);
        setError('');
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [place.script, changes]);

  // Her page asks for a view of this page, or says one of her tools changed something.
  useSerafinaRequests({
    open: (search) => go(placeFrom(search), true),
    changed: () => setChanges((c) => c + 1),
  });

  useEffect(() => {
    if (place.script === null) showOnScreen({ label: 'Your scripts' });
    else if (script && place.view !== 'rehearse') {
      showOnScreen({ label: `${script.title} · ${place.view}`, items: [{ kind: 'script', id: String(script.id) }] });
    }
  }, [place, script]);

  const open = (id: number, view: View = 'rehearse', focus: number | null = null) => go({ script: id, view, focus });

  if (place.script === null) {
    return (
      <div className="flex min-h-[100dvh] flex-col pb-[env(safe-area-inset-bottom)]">
        <AppBar title="Lines" />
        <Library
          onOpen={(id) => open(id)}
          onAdded={(s) => {
            setScript(s);
            open(s.id, 'review');
          }}
          changes={changes}
        />
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col">
      <AppBar title={script?.title ?? 'Lines'} onBack={() => go({ script: null, view: 'rehearse', focus: null })} />
      <div className="flex items-center gap-2 border-b border-ink-800 px-3 py-2">
        <Segmented
          label="View"
          value={place.view}
          options={[
            { value: 'rehearse', label: 'Rehearse' },
            { value: 'script', label: 'Script' },
            { value: 'progress', label: 'Progress' },
            { value: 'review', label: 'Fix' },
          ]}
          onChange={(view) => go({ ...place, view, focus: null }, true)}
        />
        {script && (
          <button type="button" className={`${iconButton} hidden md:flex`} title="Ask about this scene"
            onClick={() => askAbout({ label: script.title, items: [{ kind: 'script', id: String(script.id) }] })}>
            <MessageCircle className="h-4 w-4" />
          </button>
        )}
      </div>
      {error && <div className="p-3"><ErrorBanner>{error}</ErrorBanner></div>}
      {!script && !error && <Spinner className="mx-auto mt-8 h-5 w-5 text-ink-500" />}
      {script && (
        <div className={`flex min-h-0 flex-1 flex-col ${place.view === 'rehearse' ? '' : 'overflow-y-auto pb-24'}`}>
          {place.view === 'rehearse' && (
            <Rehearse script={script} onScript={setScript} onReview={() => open(script.id, 'review')} changes={changes} />
          )}
          {place.view === 'script' && (
            <ScriptView
              script={script}
              onScript={setScript}
              onRehearse={() => {
                setChanges((c) => c + 1);
                open(script.id, 'rehearse');
              }}
              onEdit={(element) => open(script.id, 'review', element)}
              focus={place.focus}
            />
          )}
          {place.view === 'progress' && (
            <Progress
              script={script}
              changes={changes}
              onDrill={() => {
                void api.drill(script.id).then(() => {
                  setChanges((c) => c + 1);
                  open(script.id, 'rehearse');
                });
              }}
              onLine={(element) => open(script.id, 'script', element)}
            />
          )}
          {place.view === 'review' && (
            <Review script={script} onScript={setScript} onRehearse={() => open(script.id, 'rehearse')} focus={place.focus} />
          )}
        </div>
      )}
    </div>
  );
}
