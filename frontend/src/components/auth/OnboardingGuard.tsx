/**
 * Onboarding Guard Component
 * Checks if user needs to complete onboarding before accessing the app.
 *
 * If the backend says onboarding is required BUT the user previously
 * clicked "Skip setup", we honour the skip (localStorage flag) so the
 * user is never stuck in a redirect loop.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useOnboardingCheck } from '@/api/onboarding';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/common/LoadingSpinner';

const SKIP_KEY = 'stratum_onboarding_skipped';

interface OnboardingGuardProps {
  children: React.ReactNode;
}

export default function OnboardingGuard({ children }: OnboardingGuardProps) {
  const location = useLocation();
  const { user } = useAuth();
  const { data, isLoading, error } = useOnboardingCheck();
  const canRunSetup = user?.role === 'owner' || user?.role === 'admin';

  // Checked BEFORE isLoading. This used to sit below the loading branch,
  // which made it unreachable exactly when it was needed: a user who had
  // already skipped onboarding still waited on the probe, and if the probe
  // hung they never got in at all. A recorded skip is a decision already
  // made — no readiness check can change it.
  if (localStorage.getItem(SKIP_KEY) === 'true') {
    return <>{children}</>;
  }

  // Show loading while checking onboarding status. Bounded: the probe uses a
  // 5s timeout and does not retry (see useOnboardingCheck), so this resolves
  // one way or the other rather than blocking the dashboard indefinitely.
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    );
  }

  // If there's an error checking onboarding, allow through (fail open)
  // The dashboard will handle showing appropriate error states
  if (error) {
    return <>{children}</>;
  }

  // If onboarding is required and user can run setup, redirect to onboarding
  if (data?.required && canRunSetup) {
    // Preserve the intended destination so we can redirect after onboarding
    return <Navigate to="/onboarding" state={{ from: location }} replace />;
  }

  // Onboarding complete, render children
  return <>{children}</>;
}
