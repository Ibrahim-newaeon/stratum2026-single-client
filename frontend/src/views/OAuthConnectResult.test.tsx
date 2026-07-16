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
