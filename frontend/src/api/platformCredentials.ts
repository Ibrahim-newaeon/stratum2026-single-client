/**
 * ADs Growth System - Platform app credential management (Integrations page).
 *
 * Wraps /platform-credentials: per-platform field specs, write-only secret
 * upserts, and live connection tests. Secrets are never returned by the API;
 * `extra_configured` lists which optional fields hold a value.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiResponse } from './client';

export interface CredentialFieldSpec {
  key: string;
  label: string;
  required: boolean;
  secret: boolean;
  maps_to: 'client_id' | 'client_secret' | 'developer_token' | 'extra';
  help: string;
}

export interface CredentialStatus {
  platform: string;
  label: string;
  configured: boolean;
  source: 'database' | 'environment' | null;
  client_id: string | null;
  has_developer_token: boolean;
  callback_url: string;
  oauth: boolean;
  fields: CredentialFieldSpec[];
  extra_configured: string[];
}

export interface CredentialUpsert {
  client_id: string;
  client_secret?: string;
  developer_token?: string;
  extra?: Record<string, string>;
}

export interface ConnectionTestResult {
  platform: string;
  ok: boolean;
  status: 'valid' | 'invalid' | 'configured_unverified' | 'not_configured' | 'unreachable';
  detail: string;
  metadata?: Record<string, unknown> | null;
}

const KEY = ['platform-credentials'];

export function usePlatformCredentials() {
  return useQuery({
    queryKey: KEY,
    queryFn: async (): Promise<CredentialStatus[]> => {
      const res = await apiClient.get<ApiResponse<CredentialStatus[]>>('/platform-credentials');
      return res.data.data ?? [];
    },
    staleTime: 30 * 1000,
    retry: false,
  });
}

export function useSaveCredentials() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ platform, payload }: { platform: string; payload: CredentialUpsert }) => {
      const res = await apiClient.put<ApiResponse<CredentialStatus>>(
        `/platform-credentials/${platform}`,
        payload
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (platform: string): Promise<ConnectionTestResult> => {
      const res = await apiClient.post<ApiResponse<ConnectionTestResult>>(
        `/platform-credentials/${platform}/test`,
        {}
      );
      if (!res.data.data) throw new Error('Empty test response');
      return res.data.data;
    },
  });
}
