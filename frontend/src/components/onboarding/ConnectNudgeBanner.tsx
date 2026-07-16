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
  const { hasLiveConnection, isLoading, isError } = useConnections();

  const onboardingSettled = !onboarding.isLoading && onboarding.data?.required === false;
  if (dismissed || isLoading || isError || hasLiveConnection || !onboardingSettled) return null;

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
