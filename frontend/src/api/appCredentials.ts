/**
 * ADs Growth System - Platform app credentials (owner/admin).
 *
 * Per-deployment OAuth application credentials, managed in the UI for the
 * black-box model. Secrets are write-only: sent on save, never read back.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiResponse } from './client';
import type { AdPlatform } from './connections';

export const CREDENTIALS_NOT_CONFIGURED = 'credentials_not_configured';

export interface AppCredentialStatus {
  platform: AdPlatform;
  configured: boolean;
  source: 'database' | 'environment' | null;
  client_id: string | null;
  has_developer_token: boolean;
  callback_url: string;
}

export interface SaveCredentialsInput {
  platform: AdPlatform;
  client_id: string;
  client_secret?: string;
  developer_token?: string;
}

export function useAppCredentials(enabled = true) {
  const query = useQuery({
    queryKey: ['app-credentials'],
    queryFn: async (): Promise<AppCredentialStatus[]> => {
      const res =
        await apiClient.get<ApiResponse<AppCredentialStatus[]>>(
          '/platform-credentials'
        );
      return res.data.data ?? [];
    },
    enabled,
    retry: false, // 403 for non-admins — do not hammer
    staleTime: 60 * 1000,
  });
  return { ...query, credentials: query.data ?? [] };
}

function useInvalidateCredentialQueries() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['app-credentials'] });
    queryClient.invalidateQueries({ queryKey: ['connections'] });
  };
}

export function useSaveAppCredentials() {
  const invalidate = useInvalidateCredentialQueries();
  return useMutation({
    mutationFn: async ({ platform, client_id, client_secret, developer_token }: SaveCredentialsInput) => {
      const res = await apiClient.put<ApiResponse<AppCredentialStatus>>(
        `/platform-credentials/${platform}`,
        { client_id, client_secret, developer_token }
      );
      return res.data.data;
    },
    onSuccess: invalidate,
  });
}

export function useDeleteAppCredentials() {
  const invalidate = useInvalidateCredentialQueries();
  return useMutation({
    mutationFn: async (platform: AdPlatform) => {
      await apiClient.delete(`/platform-credentials/${platform}`);
    },
    onSuccess: invalidate,
  });
}
