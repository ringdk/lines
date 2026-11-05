// Relative on purpose: inside Serafina the page is /api/apps/lines/, and
// her proxy signs every request to it with who's signed in.

export interface Note {
  id: number;
  body: string;
  created_at: string;
}

export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`api/${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
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

export const api = {
  notes: () => call<Note[]>('notes'),
  add: (text: string) => call<Note>('notes', { method: 'POST', body: JSON.stringify({ text }) }),
  remove: (id: number) => call<{ deleted: boolean }>(`notes/${id}/delete`, { method: 'POST' }),
};
