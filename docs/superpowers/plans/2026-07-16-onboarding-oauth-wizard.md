# Onboarding OAuth Wizard Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the onboarding wizard's Platform step perform real OAuth connections (soft-gated), add the missing `/connect` OAuth landing route, fix the broken IntegrationsHub Connect button, and show a session-dismissible "connect your first platform" banner until the first live connection exists.

**Architecture:** All connection state flows through one new React-Query hook (`useConnections`, `queryKey: ['connections']`, wrapping `GET /oauth/status`) and one shared helper (`startOAuthConnect`) that calls `POST /oauth/{platform}/authorize`, stashes a return path in `sessionStorage`, and returns the `authorization_url` for the caller to navigate to. OAuth is full-page redirect; the backend callback already redirects to `{frontend_url}/connect?platform=&status=&error=`, which gets a new landing view that invalidates queries and routes back. One backend line changes (allow empty platform selection).

**Tech Stack:** React 18 + TypeScript, @tanstack/react-query, react-router-dom v6, vitest + @testing-library/react, FastAPI + Pydantic (one validator change), shadcn `useToast`.

**Spec:** `docs/superpowers/specs/2026-07-16-onboarding-oauth-wizard-design.md`

## Global Constraints

- Frontend imports use the `@/` alias (maps to `frontend/src/`).
- Toasts: `const { toast } = useToast()` from `@/components/ui/use-toast`; call shape `toast({ title, description, variant?: 'destructive' })`.
- API calls: `apiClient` from `@/api/client`; responses are wrapped — read `response.data.data` (type helper `ApiResponse<T>`).
- Styling: semantic Tailwind tokens only (`bg-card`, `text-muted-foreground`, `border-border`, `text-primary`) — no hardcoded hex.
- Session keys (exact strings): `stratum_oauth_return`, `stratum_connect_nudge_dismissed`.
- Backend: type hints required; run backend tests with `python -m pytest` from `backend/`.
- Frontend tests colocate as `*.test.ts(x)` next to the source. Run with `npx vitest run <path>` from `frontend/`.
- Conventional commits: `feat|fix|test|docs(scope): message`.
- Commit messages end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Never log or persist tokens; the frontend only ever sees `authorization_url`, never credentials.

---

### Task 1: Backend — allow empty platform selection

**Files:**
- Modify: `backend/app/api/v1/endpoints/onboarding.py:91-98`
- Test: `backend/tests/unit/test_onboarding_platform_selection_schema.py` (create)

**Interfaces:**
- Produces: `POST /onboarding/platform-selection` accepts `{"platforms": []}` (used by Task 5's zero-connection Continue).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_onboarding_platform_selection_schema.py
"""PlatformSelectionRequest must allow an empty list (soft-gate onboarding)."""

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.onboarding import PlatformSelectionRequest


def test_empty_platform_list_is_valid() -> None:
    req = PlatformSelectionRequest(platforms=[])
    assert req.platforms == []


def test_platform_names_still_validated() -> None:
    with pytest.raises(ValidationError):
        PlatformSelectionRequest(platforms=["myspace"])


def test_platform_names_lowercased() -> None:
    req = PlatformSelectionRequest(platforms=["Meta", "google"])
    assert req.platforms == ["meta", "google"]
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python -m pytest tests/unit/test_onboarding_platform_selection_schema.py -v`
Expected: `test_empty_platform_list_is_valid` FAILS with `ValidationError` (min_length); the other two PASS.

- [ ] **Step 3: Implement — remove the min_length constraint**

In `backend/app/api/v1/endpoints/onboarding.py`, change:

```python
    platforms: list[str] = Field(
        ...,
        min_length=1,
        description="List of platforms: meta, google, tiktok, snapchat",
    )
```

to:

```python
    platforms: list[str] = Field(
        ...,
        description=(
            "List of platforms: meta, google, tiktok, snapchat. "
            "May be empty — onboarding is soft-gated on connections."
        ),
    )
```

(Keep the `validate_platforms` field validator unchanged.)

- [ ] **Step 4: Run tests to verify all pass**

Run: `python -m pytest tests/unit/test_onboarding_platform_selection_schema.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/onboarding.py backend/tests/unit/test_onboarding_platform_selection_schema.py
git commit -m "feat(onboarding): allow empty platform selection for soft-gated wizard"
```

---

### Task 2: `useConnections` hook + `startOAuthConnect` helper

**Files:**
- Create: `frontend/src/api/connections.ts`
- Test: `frontend/src/api/connections.test.tsx`

**Interfaces:**
- Consumes: `apiClient`, `ApiResponse` from `@/api/client`.
- Produces (used by Tasks 3–7):
  - `type AdPlatform = 'meta' | 'google' | 'tiktok' | 'snapchat'`
  - `interface PlatformConnection { platform: AdPlatform; status: 'connected' | 'expired' | 'error' | 'disconnected'; connected_at?: string | null; token_expires_at?: string | null; ad_accounts_count?: number | null; last_error?: string | null }`
  - `useConnections(enabled?: boolean): UseQueryResult<PlatformConnection[]> & { hasLiveConnection: boolean; connectedPlatforms: AdPlatform[] }` — well, exposed as a plain object: `{ connections, isLoading, hasLiveConnection, connectedPlatforms }` (see code).
  - `startOAuthConnect(platform: AdPlatform, returnTo: string): Promise<string | null>` — sets `sessionStorage['stratum_oauth_return'] = returnTo`, POSTs authorize, returns `authorization_url` (also accepting legacy `auth_url`/`redirect_url` keys) or `null` if the response has no URL.
  - `OAUTH_RETURN_KEY = 'stratum_oauth_return'`
  - Query key: `['connections']`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/api/connections.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

import { apiClient } from '@/api/client';
import { useConnections, startOAuthConnect, OAUTH_RETURN_KEY } from './connections';

const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe('useConnections', () => {
  it('derives hasLiveConnection and connectedPlatforms', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        data: [
          { platform: 'meta', status: 'connected' },
          { platform: 'google', status: 'disconnected' },
        ],
      },
    } as never);
    const { result } = renderHook(() => useConnections(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasLiveConnection).toBe(true);
    expect(result.current.connectedPlatforms).toEqual(['meta']);
  });

  it('reports no live connection when all disconnected', async () => {
    mockedGet.mockResolvedValueOnce({ data: { data: [] } } as never);
    const { result } = renderHook(() => useConnections(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasLiveConnection).toBe(false);
    expect(result.current.connectedPlatforms).toEqual([]);
  });
});

describe('startOAuthConnect', () => {
  it('stores return path and returns authorization_url', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { data: { authorization_url: 'https://meta.example/auth' } },
    } as never);
    const url = await startOAuthConnect('meta', '/onboarding');
    expect(sessionStorage.getItem(OAUTH_RETURN_KEY)).toBe('/onboarding');
    expect(mockedPost).toHaveBeenCalledWith('/oauth/meta/authorize', {});
    expect(url).toBe('https://meta.example/auth');
  });

  it('falls back to legacy auth_url key and returns null when absent', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { data: { auth_url: 'https://legacy.example/auth' } },
    } as never);
    expect(await startOAuthConnect('google', '/x')).toBe('https://legacy.example/auth');

    mockedPost.mockResolvedValueOnce({ data: { data: {} } } as never);
    expect(await startOAuthConnect('google', '/x')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/api/connections.test.tsx`
Expected: FAIL — `Cannot find module './connections'`.

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/api/connections.ts
/**
 * Stratum AI - Ad platform connection state + OAuth launch helper.
 *
 * Single source of truth for "which platforms are live" (GET /oauth/status)
 * and the shared authorize-then-redirect launcher used by the onboarding
 * wizard and the Integrations hub.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient, ApiResponse } from './client';

export type AdPlatform = 'meta' | 'google' | 'tiktok' | 'snapchat';

export interface PlatformConnection {
  platform: AdPlatform;
  status: 'connected' | 'expired' | 'error' | 'disconnected';
  connected_at?: string | null;
  token_expires_at?: string | null;
  ad_accounts_count?: number | null;
  error?: string | null;
}

/** sessionStorage key holding the in-app path to resume after OAuth. */
export const OAUTH_RETURN_KEY = 'stratum_oauth_return';

export function useConnections(enabled = true) {
  const query = useQuery({
    queryKey: ['connections'],
    queryFn: async (): Promise<PlatformConnection[]> => {
      const res =
        await apiClient.get<ApiResponse<PlatformConnection[]>>('/oauth/status');
      return res.data.data ?? [];
    },
    enabled,
    staleTime: 30 * 1000,
  });

  const connections = query.data ?? [];
  const connectedPlatforms = connections
    .filter((c) => c.status === 'connected')
    .map((c) => c.platform);

  return {
    ...query,
    connections,
    connectedPlatforms,
    hasLiveConnection: connectedPlatforms.length > 0,
  };
}

/**
 * Start the OAuth handshake for a platform.
 *
 * Stores `returnTo` (an in-app path) under OAUTH_RETURN_KEY so the /connect
 * landing route knows where to resume, then returns the provider consent URL.
 * The caller performs the actual navigation (`window.location.assign(url)`)
 * so this stays unit-testable. Returns null when the response carries no URL.
 */
export async function startOAuthConnect(
  platform: AdPlatform,
  returnTo: string
): Promise<string | null> {
  sessionStorage.setItem(OAUTH_RETURN_KEY, returnTo);
  const res = await apiClient.post<
    ApiResponse<{ authorization_url?: string; auth_url?: string; redirect_url?: string }>
  >(`/oauth/${platform}/authorize`, {});
  const d = res.data.data ?? {};
  return d.authorization_url || d.auth_url || d.redirect_url || null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/api/connections.test.tsx`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/connections.ts frontend/src/api/connections.test.tsx
git commit -m "feat(connections): useConnections hook + startOAuthConnect helper"
```

---

### Task 3: `/connect` OAuth landing route

**Files:**
- Create: `frontend/src/views/OAuthConnectResult.tsx`
- Test: `frontend/src/views/OAuthConnectResult.test.tsx`
- Modify: `frontend/src/App.tsx` (register routes)

**Interfaces:**
- Consumes: `OAUTH_RETURN_KEY` from `@/api/connections` (Task 2).
- Produces: routes `/connect` and `/dashboard/campaigns/connect` that consume `?platform=&status=&error=`, invalidate `['connections']` + `['onboarding']`, toast, and `navigate(returnTo, { replace: true })` with fallback `/dashboard/settings/integrations`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/views/OAuthConnectResult.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const toastSpy = vi.fn();
vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

import OAuthConnectResult from './OAuthConnectResult';
import { OAUTH_RETURN_KEY } from '@/api/connections';

function renderAt(url: string, qc: QueryClient) {
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/connect" element={<OAuthConnectResult />} />
          <Route path="/onboarding" element={<div>WIZARD</div>} />
          <Route path="/dashboard/settings" element={<div>SETTINGS</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe('OAuthConnectResult', () => {
  it('on success: invalidates queries, toasts, returns to stored path', async () => {
    sessionStorage.setItem(OAUTH_RETURN_KEY, '/onboarding');
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { findByText } = renderAt('/connect?platform=meta&status=success', qc);

    await findByText('WIZARD');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['connections'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['onboarding'] });
    expect(toastSpy).toHaveBeenCalledWith(
      expect.objectContaining({ title: expect.stringMatching(/connected/i) })
    );
    expect(sessionStorage.getItem(OAUTH_RETURN_KEY)).toBeNull();
  });

  it('on error: destructive toast, still returns', async () => {
    sessionStorage.setItem(OAUTH_RETURN_KEY, '/onboarding');
    const { findByText } = renderAt(
      '/connect?platform=google&status=error&error=access_denied',
      new QueryClient()
    );
    await findByText('WIZARD');
    expect(toastSpy).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'destructive' })
    );
  });

  it('falls back to integrations settings when no return path stored', async () => {
    const { findByText } = renderAt('/connect?platform=meta&status=success', new QueryClient());
    await waitFor(async () => {
      await findByText('SETTINGS');
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/views/OAuthConnectResult.test.tsx`
Expected: FAIL — `Cannot find module './OAuthConnectResult'`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/views/OAuthConnectResult.tsx
/**
 * OAuth callback landing route (/connect and /dashboard/campaigns/connect).
 *
 * The backend OAuth callback redirects the browser here with
 * ?platform=&status=success|error[&error=message]. This view is a router,
 * not a page: it refreshes connection/onboarding state, toasts the outcome,
 * and sends the user back to where the handshake started.
 */

import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { OAUTH_RETURN_KEY } from '@/api/connections';

const FALLBACK_RETURN = '/dashboard/settings/integrations';

const PLATFORM_LABELS: Record<string, string> = {
  meta: 'Meta Ads',
  google: 'Google Ads',
  tiktok: 'TikTok Ads',
  snapchat: 'Snapchat Ads',
};

export default function OAuthConnectResult() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const platform = params.get('platform') ?? '';
    const status = params.get('status');
    const label = PLATFORM_LABELS[platform] ?? platform;

    queryClient.invalidateQueries({ queryKey: ['connections'] });
    queryClient.invalidateQueries({ queryKey: ['onboarding'] });

    if (status === 'success') {
      toast({
        title: `${label} connected`,
        description: 'Campaign data sync has started in the background.',
      });
    } else if (status === 'error') {
      toast({
        title: `Couldn't connect ${label}`,
        description: params.get('error') ?? 'The platform reported an error. Try again.',
        variant: 'destructive',
      });
    }

    const returnTo = sessionStorage.getItem(OAUTH_RETURN_KEY) || FALLBACK_RETURN;
    sessionStorage.removeItem(OAUTH_RETURN_KEY);
    navigate(returnTo, { replace: true });
  }, [params, navigate, queryClient, toast]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Loader2 className="w-8 h-8 animate-spin text-primary" aria-label="Finishing connection" />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/views/OAuthConnectResult.test.tsx`
Expected: 3 PASS.

- [ ] **Step 5: Register the routes in `App.tsx`**

Add with the other `lazyWithRetry` view imports:

```tsx
const OAuthConnectResult = lazyWithRetry(() => import('./views/OAuthConnectResult'));
```

Register **two** routes:

1. Top-level, next to the existing `/onboarding` route (inside `ProtectedRoute`, NOT inside `OnboardingGuard` — the guard could redirect before the handler runs):

```tsx
<Route
  path="/connect"
  element={
    <ProtectedRoute>
      <LazyRoute>
        <OAuthConnectResult />
      </LazyRoute>
    </ProtectedRoute>
  }
/>
```

2. Inside the `/dashboard` children (un-deads existing links to `/dashboard/campaigns/connect`):

```tsx
<Route path="campaigns/connect" element={<LazyRoute><OAuthConnectResult /></LazyRoute>} />
```

- [ ] **Step 6: Verify the app builds**

Run: `npm run build`
Expected: build succeeds (tsc + vite).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/OAuthConnectResult.tsx frontend/src/views/OAuthConnectResult.test.tsx frontend/src/App.tsx
git commit -m "feat(oauth): /connect landing route for OAuth callback returns"
```

---

### Task 4: Fix IntegrationsHub Connect

**Files:**
- Modify: `frontend/src/views/operate/IntegrationsHub.tsx:127-145` (and the `PlatformStatusRow` type at `:46-53`)

**Interfaces:**
- Consumes: `startOAuthConnect` from `@/api/connections` (Task 2).

- [ ] **Step 1: Replace `handleConnect`**

```tsx
import { startOAuthConnect } from '@/api/connections';
import { useLocation } from 'react-router-dom'; // merge into the existing react-router-dom import if present

// inside the component:
const location = useLocation();

const handleConnect = async (platform: AdPlatform) => {
  setActionPlatform(platform);
  try {
    const url = await startOAuthConnect(platform, location.pathname + location.search);
    if (url) {
      window.location.assign(url);
      return;
    }
    await fetchStatuses();
  } catch {
    await fetchStatuses();
  } finally {
    setActionPlatform(null);
  }
};
```

- [ ] **Step 2: Align the status field names**

In `PlatformStatusRow` (`:46-53`) rename `expires_at` → `token_expires_at` and `account_count` → `ad_accounts_count` (matching backend `ConnectionStatusResponse`), and update the JSX below that renders those two fields (search the file for `expires_at` and `account_count` usages).

- [ ] **Step 3: Verify**

Run: `npm run build && npx vitest run src/views/operate` (no tests may exist for this view — build passing and existing suite green is the gate).
Expected: build succeeds; no test regressions.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/operate/IntegrationsHub.tsx
git commit -m "fix(integrations): launch OAuth via authorization_url; align status field names"
```

---

### Task 5: Wizard Step 2 — real connections, soft gate

**Files:**
- Modify: `frontend/src/views/Onboarding.tsx` (step-2 render `:586-623`, `handleNext` case `platform_selection` `:266-278`, `togglePlatform` `:362-369`)
- Test: `frontend/src/views/Onboarding.step2.test.tsx` (create)

**Interfaces:**
- Consumes: `useConnections`, `startOAuthConnect` from `@/api/connections`; `StatusPill` from `@/components/primitives/StatusPill`.
- Produces: step-2 UX per spec — Connect button per card, status chips, connected cards locked selected, zero-connection Continue relabeled with warning, submit union of connected+toggled.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/views/Onboarding.step2.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const submitPlatformSelection = vi.fn().mockResolvedValue({});
const startOAuthConnectMock = vi.fn();
let mockConnections: { connectedPlatforms: string[]; hasLiveConnection: boolean };

vi.mock('@/api/onboarding', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useOnboardingStatus: () => ({
      data: {
        status: 'in_progress',
        current_step: 'platform_selection',
        completed_steps: ['business_profile'],
        trust_gate_config: {
          trust_threshold_autopilot: 70,
          trust_threshold_alert: 40,
          require_approval_above: null,
          max_daily_actions: 10,
        },
      },
      isLoading: false,
    }),
    useSkipOnboarding: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitBusinessProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitPlatformSelection: () => ({ mutateAsync: submitPlatformSelection, isPending: false }),
    useSubmitGoalsSetup: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitAutomationPreferences: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitTrustGateConfig: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

vi.mock('@/api/connections', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useConnections: () => ({
      connections: [],
      connectedPlatforms: mockConnections.connectedPlatforms,
      hasLiveConnection: mockConnections.hasLiveConnection,
      isLoading: false,
    }),
    startOAuthConnect: startOAuthConnectMock,
  };
});

import Onboarding from './Onboarding';

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/onboarding']}>
        <Onboarding />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockConnections = { connectedPlatforms: [], hasLiveConnection: false };
});

describe('Onboarding step 2 (platform connections)', () => {
  it('renders a Connect button per platform and launches OAuth', async () => {
    startOAuthConnectMock.mockResolvedValue(null); // no navigation in jsdom
    renderWizard();
    const buttons = await screen.findAllByRole('button', { name: /^connect$/i });
    expect(buttons).toHaveLength(4);
    fireEvent.click(buttons[0]);
    await waitFor(() =>
      expect(startOAuthConnectMock).toHaveBeenCalledWith('meta', '/onboarding')
    );
  });

  it('zero connections: Continue relabels, warns, and submits without blocking', async () => {
    renderWizard();
    const cont = await screen.findByRole('button', { name: /continue without connecting/i });
    expect(screen.getByText(/demo data/i)).toBeInTheDocument();
    fireEvent.click(cont);
    await waitFor(() =>
      expect(submitPlatformSelection).toHaveBeenCalledWith({ platforms: [] })
    );
  });

  it('a connected platform shows as connected and is included in the submit', async () => {
    mockConnections = { connectedPlatforms: ['meta'], hasLiveConnection: true };
    renderWizard();
    expect(await screen.findByText(/^connected$/i)).toBeInTheDocument();
    const cont = screen.getByRole('button', { name: /^continue$/i });
    fireEvent.click(cont);
    await waitFor(() =>
      expect(submitPlatformSelection).toHaveBeenCalledWith({ platforms: ['meta'] })
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/views/Onboarding.step2.test.tsx`
Expected: FAIL — no Connect buttons found / old "Select Platforms" validation fires.

- [ ] **Step 3: Implement in `Onboarding.tsx`**

3a. Imports:

```tsx
import { useConnections, startOAuthConnect } from '@/api/connections';
import { StatusPill } from '@/components/primitives/StatusPill';
```

3b. Inside the component, after the existing hooks:

```tsx
const { connections, connectedPlatforms, hasLiveConnection } = useConnections();
const [connectingPlatform, setConnectingPlatform] = useState<AdPlatform | null>(null);

const handleConnectPlatform = async (platform: AdPlatform) => {
  setConnectingPlatform(platform);
  try {
    const url = await startOAuthConnect(platform, '/onboarding');
    if (url) {
      window.location.assign(url);
      return;
    }
    toast({
      title: 'Connection unavailable',
      description: 'Could not start the connection. Try again or continue without connecting.',
      variant: 'destructive',
    });
  } catch {
    toast({
      title: 'Connection failed',
      description: 'Could not start the connection. Try again or continue without connecting.',
      variant: 'destructive',
    });
  } finally {
    setConnectingPlatform(null);
  }
};

const effectivePlatforms = Array.from(
  new Set<AdPlatform>([...connectedPlatforms, ...formData.platforms])
);
```

3c. Replace the `platform_selection` case in `handleNext` (`:266-278`) — the ≥1 validation goes away:

```tsx
case 'platform_selection':
  await submitPlatformSelection.mutateAsync({
    platforms: effectivePlatforms,
  });
  break;
```

3d. In `togglePlatform`, ignore already-connected platforms (they can't be deselected):

```tsx
const togglePlatform = (platform: AdPlatform) => {
  if (connectedPlatforms.includes(platform)) return;
  setFormData((prev) => ({
    ...prev,
    platforms: prev.platforms.includes(platform)
      ? prev.platforms.filter((p) => p !== platform)
      : [...prev.platforms, platform],
  }));
};
```

3e. Replace the step-2 render block (`:586-623`). Each card keeps the toggle affordance but gains a status chip and a Connect button (`stopPropagation` so Connect doesn't toggle). Below the grid, the zero-connection warning:

```tsx
{step.id === 'platform_selection' && (
  <>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {PLATFORMS.map((p) => {
        const connection = connections.find((c) => c.platform === p.value);
        const isConnected = connectedPlatforms.includes(p.value);
        const isSelected = isConnected || formData.platforms.includes(p.value);
        const chipVariant =
          connection?.status === 'connected'
            ? 'healthy'
            : connection?.status === 'error' || connection?.status === 'expired'
              ? 'unhealthy'
              : 'neutral';
        return (
          <div
            key={p.value}
            role="button"
            tabIndex={0}
            onClick={() => togglePlatform(p.value)}
            onKeyDown={(e) => e.key === 'Enter' && togglePlatform(p.value)}
            className={cn(
              'p-4 rounded-xl border-2 text-left transition-colors cursor-pointer',
              isSelected
                ? 'border-primary bg-primary/5'
                : 'border-muted hover:border-muted-foreground/50'
            )}
          >
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'w-10 h-10 rounded-lg flex items-center justify-center text-white',
                  p.color
                )}
              >
                {p.value[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{p.label}</p>
                <StatusPill variant={chipVariant} size="sm">
                  {connection?.status === 'connected'
                    ? 'Connected'
                    : connection?.status === 'error' || connection?.status === 'expired'
                      ? 'Needs attention'
                      : 'Not connected'}
                </StatusPill>
              </div>
              {!isConnected && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleConnectPlatform(p.value);
                  }}
                  disabled={connectingPlatform === p.value}
                  className="ml-auto shrink-0 rounded-full px-4 py-1.5 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {connectingPlatform === p.value ? 'Opening…' : 'Connect'}
                </button>
              )}
              {isConnected && <Check className="w-5 h-5 text-primary ml-auto shrink-0" />}
            </div>
          </div>
        );
      })}
    </div>
    {!hasLiveConnection && (
      <p className="mt-4 text-sm text-warning" role="status">
        No platform connected yet — your dashboard will show demo data until you
        connect one. You can always connect later from Settings → Integrations.
      </p>
    )}
  </>
)}
```

Note: `StatusPill`'s exact prop names are in
`frontend/src/components/primitives/StatusPill.tsx` (`variant`, `size`) — check the
file when wiring and adjust if its children/label API differs.

3f. Relabel the footer Continue button when on step 2 with nothing selected/connected. Find the footer's next-button JSX (renders the "Continue" label near the `handleNext` wiring) and make the label conditional:

```tsx
{step.id === 'platform_selection' && effectivePlatforms.length === 0
  ? 'Continue without connecting'
  : 'Continue'}
```

- [ ] **Step 4: Run tests**

Run: `npx vitest run src/views/Onboarding.step2.test.tsx`
Expected: 3 PASS. Also run any pre-existing Onboarding tests: `npx vitest run src/views --silent` — no regressions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Onboarding.tsx frontend/src/views/Onboarding.step2.test.tsx
git commit -m "feat(onboarding): real OAuth connects in platform step with soft gate"
```

---

### Task 6: `ConnectNudgeBanner`

**Files:**
- Create: `frontend/src/components/onboarding/ConnectNudgeBanner.tsx`
- Test: `frontend/src/components/onboarding/ConnectNudgeBanner.test.tsx`
- Modify: `frontend/src/views/DashboardLayout.tsx:302` (mount next to `OnboardingChecklist`)

**Interfaces:**
- Consumes: `useConnections` (Task 2), `useOnboardingCheck` from `@/api/onboarding`.
- Produces: `<ConnectNudgeBanner />` self-contained; session key `stratum_connect_nudge_dismissed`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/onboarding/ConnectNudgeBanner.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let mockOnboarding: { data?: { required: boolean }; isLoading: boolean };
let mockConn: { hasLiveConnection: boolean; isLoading: boolean };

vi.mock('@/api/onboarding', () => ({
  useOnboardingCheck: () => mockOnboarding,
}));
vi.mock('@/api/connections', () => ({
  useConnections: () => mockConn,
}));

import { ConnectNudgeBanner } from './ConnectNudgeBanner';

function renderBanner() {
  return render(
    <MemoryRouter>
      <ConnectNudgeBanner />
    </MemoryRouter>
  );
}

beforeEach(() => {
  sessionStorage.clear();
  mockOnboarding = { data: { required: false }, isLoading: false };
  mockConn = { hasLiveConnection: false, isLoading: false };
});

describe('ConnectNudgeBanner', () => {
  it('shows when onboarding done/skipped and no live connection', () => {
    renderBanner();
    expect(screen.getByText(/demo data/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /connect now/i })).toHaveAttribute(
      'href',
      '/dashboard/settings/integrations'
    );
  });

  it('hidden while loading, when connected, or when onboarding still required', () => {
    mockConn = { hasLiveConnection: false, isLoading: true };
    expect(renderBanner().container).toBeEmptyDOMElement();

    mockConn = { hasLiveConnection: true, isLoading: false };
    expect(renderBanner().container).toBeEmptyDOMElement();

    mockConn = { hasLiveConnection: false, isLoading: false };
    mockOnboarding = { data: { required: true }, isLoading: false };
    expect(renderBanner().container).toBeEmptyDOMElement();
  });

  it('dismisses for the session', () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(sessionStorage.getItem('stratum_connect_nudge_dismissed')).toBe('true');
    expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/onboarding/ConnectNudgeBanner.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/components/onboarding/ConnectNudgeBanner.tsx
/**
 * Persistent post-skip nudge: shown on every dashboard page until the first
 * ad platform is connected. Dismissible per browser session.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, X } from 'lucide-react';
import { useConnections } from '@/api/connections';
import { useOnboardingCheck } from '@/api/onboarding';

const DISMISS_KEY = 'stratum_connect_nudge_dismissed';

export function ConnectNudgeBanner() {
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === 'true'
  );
  const onboarding = useOnboardingCheck();
  const { hasLiveConnection, isLoading } = useConnections();

  const onboardingSettled = !onboarding.isLoading && onboarding.data?.required === false;
  if (dismissed || isLoading || hasLiveConnection || !onboardingSettled) return null;

  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-2xl border border-border bg-card px-4 py-2.5 mb-4"
    >
      <AlertTriangle className="w-4 h-4 text-warning shrink-0" aria-hidden />
      <p className="text-sm text-muted-foreground flex-1 min-w-0">
        You&apos;re viewing demo data — connect your first ad platform to go live.
      </p>
      <Link
        to="/dashboard/settings/integrations"
        className="shrink-0 rounded-full px-4 py-1.5 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90"
      >
        Connect now
      </Link>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, 'true');
          setDismissed(true);
        }}
        className="shrink-0 p-1 rounded-full text-muted-foreground hover:text-foreground"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/onboarding/ConnectNudgeBanner.test.tsx`
Expected: 3 PASS.

- [ ] **Step 5: Mount in `DashboardLayout.tsx`**

Import and render directly above the existing checklist mount (line ~302):

```tsx
import { ConnectNudgeBanner } from '@/components/onboarding/ConnectNudgeBanner';
// ...
<ConnectNudgeBanner />
<OnboardingChecklist variant="horizontal" />
```

- [ ] **Step 6: Verify build + commit**

Run: `npm run build`

```bash
git add frontend/src/components/onboarding/ConnectNudgeBanner.tsx frontend/src/components/onboarding/ConnectNudgeBanner.test.tsx frontend/src/views/DashboardLayout.tsx
git commit -m "feat(onboarding): persistent connect-first-platform nudge banner"
```

---

### Task 7: Honest `connect_platform` checklist item

**Files:**
- Modify: `frontend/src/components/onboarding/OnboardingChecklist.tsx` (localStorage-load effect at `:122-142`)

**Interfaces:**
- Consumes: `useConnections` (Task 2).

- [ ] **Step 1: Implement**

Add the hook and override the `connect_platform` item's completion with backend truth. In the component body:

```tsx
import { useConnections } from '@/api/connections';
// inside OnboardingChecklist():
const { hasLiveConnection } = useConnections();
```

Then derive the displayed list from state + truth (place directly after the `checklist` state declarations, replacing reads of `checklist` in render/`completedCount` with `displayChecklist`):

```tsx
const displayChecklist = checklist.map((item) =>
  item.id === 'connect_platform' ? { ...item, completed: hasLiveConnection } : item
);
```

Update `completedCount`/`progress`/render loops to use `displayChecklist` (the persisted localStorage progress for other items is unchanged; `markComplete`/`saveProgress` stay as-is).

- [ ] **Step 2: Verify**

Run: `npx vitest run src/components/onboarding` — existing checklist tests (if any) plus banner tests pass.
Run: `npm run build` — clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingChecklist.tsx
git commit -m "fix(onboarding): derive connect_platform checklist state from real connections"
```

---

### Task 8: Full verification + push

- [ ] **Step 1: Frontend full suite**

Run (from `frontend/`): `npx vitest run`
Expected: all pass (966+ tests including the ~10 new ones).

- [ ] **Step 2: Frontend build**

Run: `npm run build`
Expected: tsc + vite succeed.

- [ ] **Step 3: Backend suite (touched area)**

Run (from `backend/`): `python -m pytest tests/unit -q`
Expected: pass rate matches baseline (known env-dependent errors in `test_global_uniqueness.py` are pre-existing; see memory).

- [ ] **Step 4: Push**

```bash
git push origin main
```

Then verify Railway deploy goes green and `/health` stays healthy.

**Manual E2E (user-driven, after ad-platform credentials are configured):** run the wizard on production, click Connect on Meta, complete consent, confirm return to step 2 with "Connected" chip, and confirm the nudge banner disappears after connecting.
