import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/api/client', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, apiClient: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

import { apiClient } from '@/api/client';
import { useAppCredentials, useSaveAppCredentials } from './appCredentials';

const mockedGet = vi.mocked(apiClient.get);
const mockedPut = vi.mocked(apiClient.put);

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

describe('useAppCredentials', () => {
  it('fetches the credential status list', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        data: [
          {
            platform: 'meta', configured: true, source: 'database',
            client_id: 'cid', has_developer_token: false,
            callback_url: 'https://api.example/api/v1/oauth/meta/callback',
          },
        ],
      },
    } as never);
    const { result } = renderHook(() => useAppCredentials(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockedGet).toHaveBeenCalledWith('/platform-credentials');
    expect(result.current.credentials[0].source).toBe('database');
  });
});

describe('useSaveAppCredentials', () => {
  it('PUTs to the platform path and invalidates queries', async () => {
    mockedPut.mockResolvedValueOnce({ data: { data: {} } } as never);
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useSaveAppCredentials(), { wrapper });
    await result.current.mutateAsync({
      platform: 'meta',
      client_id: 'cid',
      client_secret: 'sec',
    });
    expect(mockedPut).toHaveBeenCalledWith('/platform-credentials/meta', {
      client_id: 'cid',
      client_secret: 'sec',
      developer_token: undefined,
    });
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['app-credentials'] })
    );
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['connections'] });
  });
});
