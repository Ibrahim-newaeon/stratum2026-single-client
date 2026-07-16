/**
 * OAuth callback landing route (/connect and /dashboard/campaigns/connect).
 *
 * The backend OAuth callback redirects the browser here with either
 * ?platform=&status=success on success, or ?platform=&error=&message= on
 * failure (never status=error — see backend/app/api/v1/endpoints/oauth.py).
 * This view is a router, not a page: it refreshes connection/onboarding
 * state, toasts the outcome, and sends the user back to where the handshake
 * started.
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
    const error = params.get('error');
    const label = PLATFORM_LABELS[platform] ?? platform;

    queryClient.invalidateQueries({ queryKey: ['connections'] });
    queryClient.invalidateQueries({ queryKey: ['onboarding'] });

    if (status === 'success') {
      toast({
        title: `${label} connected`,
        description: 'Campaign data sync has started in the background.',
      });
    } else if (error || status === 'error') {
      toast({
        title: `Couldn't connect ${label}`,
        description:
          params.get('message') ?? error ?? 'The platform reported an error. Try again.',
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
