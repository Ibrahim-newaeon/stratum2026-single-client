import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const submitPlatformSelection = vi.fn().mockResolvedValue({});
// `startOAuthConnect` is referenced directly (unwrapped) at the top level of the
// `@/api/connections` mock factory below, so it must be created via `vi.hoisted`
// — otherwise the factory (invoked when Onboarding.tsx's static import of
// `@/api/connections` is evaluated, which happens before this file's own
// top-level `const`s run) sees a TDZ ReferenceError.
const startOAuthConnectMock = vi.hoisted(() => vi.fn());
let mockConnections: { connectedPlatforms: string[]; hasLiveConnection: boolean };

vi.mock('@/api/onboarding', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useOnboardingStatus: () => ({
      data: {
        status: 'in_progress',
        current_step: 'platform_selection',
        completed_steps: ['business_profile'],
        trust_gate_config: {
          trust_threshold_autopilot: 70,
          trust_threshold_alert: 40,
          require_approval_above: null,
          max_daily_actions: 10,
        },
      },
      isLoading: false,
    }),
    useSkipOnboarding: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitBusinessProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitPlatformSelection: () => ({ mutateAsync: submitPlatformSelection, isPending: false }),
    useSubmitGoalsSetup: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitAutomationPreferences: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmitTrustGateConfig: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

vi.mock('@/api/connections', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useConnections: () => ({
      connections: [],
      connectedPlatforms: mockConnections.connectedPlatforms,
      hasLiveConnection: mockConnections.hasLiveConnection,
      isLoading: false,
    }),
    startOAuthConnect: startOAuthConnectMock,
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'owner' } }),
}));

import Onboarding from './Onboarding';

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/onboarding']}>
        <Onboarding />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockConnections = { connectedPlatforms: [], hasLiveConnection: false };
});

describe('Onboarding step 2 (platform connections)', () => {
  it('renders a Connect button per platform and launches OAuth', async () => {
    startOAuthConnectMock.mockResolvedValue(null); // no navigation in jsdom
    renderWizard();
    const buttons = await screen.findAllByRole('button', { name: /^connect$/i });
    expect(buttons).toHaveLength(4);
    fireEvent.click(buttons[0]);
    await waitFor(() =>
      expect(startOAuthConnectMock).toHaveBeenCalledWith('meta', '/onboarding')
    );
  });

  it('zero connections: Continue relabels, warns, and submits without blocking', async () => {
    renderWizard();
    const cont = await screen.findByRole('button', { name: /continue without connecting/i });
    expect(screen.getByText(/demo data/i)).toBeInTheDocument();
    fireEvent.click(cont);
    await waitFor(() =>
      expect(submitPlatformSelection).toHaveBeenCalledWith({ platforms: [] })
    );
  });

  it('a connected platform shows as connected and is included in the submit', async () => {
    mockConnections = { connectedPlatforms: ['meta'], hasLiveConnection: true };
    renderWizard();
    expect(await screen.findByText(/^connected$/i)).toBeInTheDocument();
    const cont = screen.getByRole('button', { name: /^continue$/i });
    fireEvent.click(cont);
    await waitFor(() =>
      expect(submitPlatformSelection).toHaveBeenCalledWith({ platforms: ['meta'] })
    );
  });

  it('Enter on Connect does not toggle the card selection', async () => {
    startOAuthConnectMock.mockResolvedValue(null);
    renderWizard();
    const buttons = await screen.findAllByRole('button', { name: /^connect$/i });
    fireEvent.keyDown(buttons[0], { key: 'Enter' });
    // keydown must not bubble into togglePlatform: submit still sends []
    const cont = screen.getByRole('button', { name: /continue without connecting/i });
    fireEvent.click(cont);
    await waitFor(() =>
      expect(submitPlatformSelection).toHaveBeenCalledWith({ platforms: [] })
    );
  });

  it('credentials-missing error shows setup callout instead of generic toast', async () => {
    const err = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Request failed with status code 400',
      response: {
        status: 400,
        data: {
          detail: {
            code: 'credentials_not_configured',
            message:
              'Meta app credentials are not configured. An owner or admin can add them under Settings → Integrations.',
          },
        },
      },
    };
    startOAuthConnectMock.mockRejectedValueOnce(err);
    renderWizard();
    const buttons = await screen.findAllByRole('button', { name: /^connect$/i });
    fireEvent.click(buttons[0]);
    expect(
      await screen.findByText(/app credentials are not configured/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /set up credentials/i })).toHaveAttribute(
      'href',
      '/dashboard/settings/integrations'
    );
  });
});
