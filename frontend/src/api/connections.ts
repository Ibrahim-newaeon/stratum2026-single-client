/**
 * ADs Growth System - Ad platform connection state + OAuth launch helper.
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
  last_error?: string | null;
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
    retry: false,
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
