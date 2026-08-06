import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Node ≥25 pre-defines globalThis.localStorage/sessionStorage (its
// experimental Web Storage — undefined without --localstorage-file), which
// stops Vitest's jsdom environment from installing jsdom's real Storage.
// Every test that used the actual (unmocked) storage then crashed with
// "Cannot read properties of undefined". Install an in-memory Storage
// when the global is missing; per-file setup means per-file isolation.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

for (const name of ['localStorage', 'sessionStorage'] as const) {
  if (typeof (globalThis as Record<string, unknown>)[name] === 'undefined') {
    Object.defineProperty(globalThis, name, {
      value: new MemoryStorage(),
      configurable: true, // tests that mock storage still override cleanly
      writable: true,
    });
  }
}

// Auto-unmount React Testing Library trees after each test. Without
// this, every render() leaves its DOM in document.body and event
// listeners + reconciler state accumulate across the file. The
// 14 component tests in ProtectedRoute.test.tsx OOM'd the worker
// before this was wired (passes individually, hangs together).
afterEach(() => {
  cleanup();
});
