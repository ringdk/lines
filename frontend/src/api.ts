// Relative on purpose: inside Serafina the page is /api/apps/lines/, and
// her proxy signs every request to it with who's signed in.

export interface ScriptSummary {
  id: number;
  title: string;
  source: string;
  characters: string[];
  mine: string[];
  lines: number;
  mastery: number;
  updated_at: string;
}

export interface Element {
  id: number;
  pos: number;
  kind: 'line' | 'direction' | 'heading';
  character: string | null;
  text: string;
  note: string | null;
  page: number | null;
  interrupted: boolean;
}

export interface Settings {
  suggestions: boolean;
  cue_view: boolean;
  directions: boolean;
  input: 'words' | 'letters';
  level: 'auto' | 1 | 2 | 3 | 4 | 5;
  loop: { from: number; to: number } | null;
}

export interface LineState {
  score: number;
  attempts: number;
  level: number;
}

export interface Script {
  id: number;
  title: string;
  source: string;
  characters: string[];
  mine: string[];
  settings: Settings;
  elements: Element[];
  mastery: number;
  lines: Record<string, LineState>;
}

export interface Decoys {
  near: string[];
  far: string[];
}

export interface Prompt {
  id: number;
  pos: number;
  character: string;
  note: string | null;
  words: string[];
  decoys: Decoys[];
  level: number;
  label: string;
  score: number | null;
  interrupted: boolean;
}

export type Cue = Element | { kind: 'loop' };

export interface RunView {
  script: number;
  mode: 'run' | 'drill';
  settings: Settings;
  mine: string[];
  mastery: number;
  total: number;
  done?: number;
  remaining?: number;
  needs_character?: boolean;
  context: Element[];
  cues: Cue[];
  prompt: Prompt | null;
  end: boolean;
}

export type Status = 'ok' | 'minor' | 'wrong' | 'missed';

export interface GradedWord {
  lead: string;
  text: string;
  status: Status;
}

export interface Graded {
  line_id: number;
  character: string;
  note: string | null;
  words: GradedWord[];
  tail: string;
  extra: { after: number; text: string }[];
  score: number;
  complete: boolean;
}

export interface AttemptResult {
  graded: Graded;
  line: { id: number; score: number; level: number; label: string };
  view: RunView;
}

export interface Progress {
  script: number;
  mastery: number;
  label: string;
  lines: (LineState & { id: number; pos: number; text: string })[];
  weakest: (LineState & { id: number; pos: number; text: string })[];
  days: { day: string; attempts: number; accuracy: number; lines_called: number }[];
}

export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`api/${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body && typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // not JSON: the status line will do
    }
    throw new ApiError(detail);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown = {}) => call<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  scripts: () => call<ScriptSummary[]>('scripts'),
  fromText: (title: string, text: string) => post<Script>('scripts/text', { title, text }),
  fromGoogleDoc: (title: string, url: string) => post<Script>('scripts/gdoc', { title, url }),
  fromPdf: (title: string, file: File) =>
    call<Script>(`scripts/pdf?title=${encodeURIComponent(title)}`, {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': 'application/pdf' },
    }),
  script: (id: number) => call<Script>(`scripts/${id}`),
  update: (id: number, change: { title?: string; mine?: string[]; settings?: Partial<Settings> }) =>
    post<Script>(`scripts/${id}`, change),
  remove: (id: number) => post<{ deleted: boolean }>(`scripts/${id}/delete`),
  element: (id: number, element: number, change: Record<string, unknown>) =>
    post<Script>(`scripts/${id}/elements/${element}`, change),
  rename: (id: number, from: string, to: string) => post<Script>(`scripts/${id}/rename`, { from, to }),
  run: (id: number) => call<RunView>(`scripts/${id}/run`),
  attempt: (id: number, body: { line_id: number; text: string; mode: 'words' | 'letters'; helped: number; gave_up: boolean }) =>
    post<AttemptResult>(`scripts/${id}/run/attempt`, body),
  jump: (id: number, to: 'top' | 'back' | number) => post<RunView>(`scripts/${id}/run/jump`, { to }),
  drill: (id: number, count = 5) => post<RunView>(`scripts/${id}/run/drill`, { count }),
  stopDrill: (id: number) => post<RunView>(`scripts/${id}/run/stop-drill`),
  progress: (id: number) => call<Progress>(`scripts/${id}/progress`),
};
