import { useCallback, useSyncExternalStore } from 'react';

function getHash(): string {
  return window.location.hash.replace(/^#\/?/, '') || '';
}

function subscribe(cb: () => void) {
  window.addEventListener('hashchange', cb);
  return () => window.removeEventListener('hashchange', cb);
}

function parseHash(raw: string): { path: string; params: URLSearchParams } {
  const qIdx = raw.indexOf('?');
  if (qIdx === -1) return { path: raw, params: new URLSearchParams() };
  return { path: raw.slice(0, qIdx), params: new URLSearchParams(raw.slice(qIdx + 1)) };
}

function buildHash(path: string, params?: Record<string, string>): string {
  const sp = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) sp.set(k, v);
    }
  }
  const qs = sp.toString();
  return `#/${path}${qs ? '?' + qs : ''}`;
}

export function useHashRoute() {
  const raw = useSyncExternalStore(subscribe, getHash);
  const { path, params } = parseHash(raw);

  const navigate = useCallback((newPath: string, newParams?: Record<string, string>) => {
    window.location.hash = buildHash(newPath, newParams);
  }, []);

  const setParams = useCallback((updates: Record<string, string>) => {
    const current = parseHash(getHash());
    const merged: Record<string, string> = {};
    current.params.forEach((v, k) => { merged[k] = v; });
    Object.assign(merged, updates);
    window.location.hash = buildHash(current.path, merged);
  }, []);

  return { path: path || 'overview', params, navigate, setParams };
}
