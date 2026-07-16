import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let mockOnboarding: { data?: { required: boolean }; isLoading: boolean };
let mockConn: { hasLiveConnection: boolean; isLoading: boolean; isError: boolean };

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
  mockConn = { hasLiveConnection: false, isLoading: false, isError: false };
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
    mockConn = { hasLiveConnection: false, isLoading: true, isError: false };
    expect(renderBanner().container).toBeEmptyDOMElement();

    mockConn = { hasLiveConnection: true, isLoading: false, isError: false };
    expect(renderBanner().container).toBeEmptyDOMElement();

    mockConn = { hasLiveConnection: false, isLoading: false, isError: false };
    mockOnboarding = { data: { required: true }, isLoading: false };
    expect(renderBanner().container).toBeEmptyDOMElement();
  });

  it('hidden when the connections query errored (non-admin 403)', () => {
    mockConn = { hasLiveConnection: false, isLoading: false, isError: true };
    expect(renderBanner().container).toBeEmptyDOMElement();
  });

  it('dismisses for the session', () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(sessionStorage.getItem('stratum_connect_nudge_dismissed')).toBe('true');
    expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument();
  });
});
