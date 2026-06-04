import { useState, useEffect } from 'react';

export function useDebouncedValue<T>(value: T, delay: number, minLength = 0): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    if (typeof value === 'string' && value.length > 0 && value.length < minLength) return;
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay, minLength]);

  return debounced;
}
