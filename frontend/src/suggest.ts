import type { Prompt } from './api';

// The same words the server grades by: letters and digits, with apostrophes inside.
const WORD = /[A-Za-z0-9À-ɏ]+(?:['’][A-Za-zÀ-ɏ]+)*/g;

export function wordCount(text: string): number {
  return text.match(WORD)?.length ?? 0;
}

// How each level asks: how many words a chip holds, and how many chips.
// Easy levels offer a phrase against an obvious wrong one; hard ones a single
// word against words that look like it.
const SHAPE: Record<number, { size: number; count: number }> = {
  1: { size: 3, count: 2 },
  2: { size: 2, count: 3 },
  3: { size: 1, count: 3 },
  4: { size: 1, count: 4 },
  5: { size: 1, count: 4 },
};

function rng(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return (s >>> 0) / 4294967296;
  };
}

export interface Chips {
  at: number; // the word they start at
  options: string[];
  right: number; // which option is the line's
}

/** The chips for the next words of the line, after `typed`. */
export function chipsFor(prompt: Prompt, typed: string, level: number): Chips | null {
  const at = wordCount(typed);
  if (at >= prompt.words.length) return null;
  const { size, count } = SHAPE[level] ?? SHAPE[3];
  const end = Math.min(prompt.words.length, at + size);
  const right = prompt.words.slice(at, end);
  const d = prompt.decoys.slice(at, end);
  const random = rng(prompt.id * 7919 + at * 104729 + level);
  const wrong: string[][] = [];

  if (level === 1) {
    wrong.push(right.map((_, k) => d[k].far[0] ?? d[k].near[0]));
  } else if (level === 2) {
    for (const pool of ['near', 'far'] as const) {
      const k = Math.floor(random() * right.length);
      wrong.push(right.map((w, j) => (j === k ? d[j][pool][0] ?? w : w)));
    }
  } else {
    const picks =
      level === 3 ? d[0].far.slice(0, 2) : level === 4 ? [...d[0].near.slice(0, 2), ...d[0].far.slice(0, 1)] : d[0].near.slice(0, 3);
    for (const w of picks) wrong.push([w]);
  }

  const seen = new Set([right.join(' ').toLowerCase()]);
  const options = [right.join(' ')];
  for (const option of wrong) {
    const text = option.join(' ');
    if (text && !seen.has(text.toLowerCase()) && options.length < count) {
      seen.add(text.toLowerCase());
      options.push(text);
    }
  }
  // Shuffle (Fisher-Yates), keeping track of the right one.
  const order = options.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return { at, options: order.map((i) => options[i]), right: order.indexOf(0) };
}
