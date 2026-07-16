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
