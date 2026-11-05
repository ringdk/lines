import { useCallback, useEffect, useRef, useState } from 'react';

/** Confirm a destructive action with a second tap instead of a browser
    dialog (which behaves badly on phones). The first tap arms it for a few
    seconds; a second tap in that window runs the action. */
export function useTwoTap(timeoutMs = 3000) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clear = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => clear, []);

  const tap = useCallback(
    (action: () => void) => {
      if (armed) {
        clear();
        setArmed(false);
        action();
        return;
      }
      setArmed(true);
      clear();
      timer.current = setTimeout(() => setArmed(false), timeoutMs);
    },
    [armed, timeoutMs],
  );

  const reset = useCallback(() => {
    clear();
    setArmed(false);
  }, []);

  return { armed, tap, reset };
}
