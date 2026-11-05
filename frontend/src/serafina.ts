import { useEffect, useRef } from 'react';

// Lines inside Serafina: she shows it in her frame at /apps/lines/,
// with her chat panel beside it (her §53). The app never talks to her. It only
// tells the page around it what's on screen, so she knows what you mean by
// "this"; you decide whether to send it. The other way (her §55), her page
// may ask it to show one of its own views ("serafina:open") or to catch up
// after one of her tools changed something ("serafina:changed"): see
// `useSerafinaRequests`.

export interface ScreenItem {
  kind: string;
  id: string;
}

export interface Screen {
  label: string;
  items?: ScreenItem[];
}

/** True when Serafina's page is around Lines. */
export const inSerafina = window.parent !== window;

const MAX_ITEMS = 50;

function post(message: Record<string, unknown>): void {
  if (!inSerafina) return;
  // Her page is on this same origin; nothing goes anywhere else.
  window.parent.postMessage(message, window.location.origin);
}

function context(screen: Screen): Record<string, unknown> {
  return {
    label: screen.label,
    path: window.location.pathname + window.location.search,
    ...(screen.items?.length ? { items: screen.items.slice(0, MAX_ITEMS) } : {}),
  };
}

/** What's on screen now: sent with her next message while it's current. */
export function showOnScreen(screen: Screen): void {
  post({ type: 'serafina:context', context: context(screen) });
}

/** The same, and open her chat about it. */
export function askAbout(screen: Screen): void {
  post({ type: 'serafina:ask', context: context(screen) });
}

/** Hide her button while something fills the screen. */
export function setQuiet(quiet: boolean): void {
  post({ type: 'serafina:quiet', quiet });
}

export interface SerafinaRequests {
  /** Show this view of Lines (its query, `?…`). */
  open: (search: string) => void;
  /** Something on screen may have changed: load it again. */
  changed: () => void;
}

/** Act on what her page asks, and only her page: the parent window, on this
    origin. A view of this page is switched to in place, which is said at once
    so she doesn't load it as well; anything else is left for her to load. */
export function useSerafinaRequests(handlers: SerafinaRequests): void {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    if (!inSerafina) return;
    const onMessage = (e: MessageEvent) => {
      if (e.source !== window.parent || e.origin !== window.location.origin) return;
      const data = e.data as { type?: unknown; path?: unknown; id?: unknown } | null;
      if (data?.type === 'serafina:changed') {
        ref.current.changed();
        return;
      }
      if (data?.type !== 'serafina:open' || typeof data.path !== 'string') return;
      let url: URL;
      try {
        url = new URL(data.path, window.location.origin);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin || url.pathname !== window.location.pathname) return;
      post({ type: 'serafina:opened', id: data.id });
      ref.current.open(url.search);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);
}

// this app's own: helpers for what it puts on screen, to the end of the file
