import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockState = {
  role: 'owner' as string,
  credentials: [] as unknown[],
  saveMutate: vi.fn().mockResolvedValue({}),
};

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: mockState.role } }),
}));

vi.mock('@/api/appCredentials', () => ({
  useAppCredentials: () => ({
    credentials: mockState.credentials,
    isLoading: false,
    isError: false,
  }),
  useSaveAppCredentials: () => ({
    mutateAsync: mockState.saveMutate,
    isPending: false,
  }),
  useDeleteAppCredentials: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

import { PlatformCredentialsPanel } from './PlatformCredentialsPanel';

const metaStatus = {
  platform: 'meta',
  configured: false,
  source: null,
  client_id: null,
  has_developer_token: false,
  callback_url: 'https://api.example/api/v1/oauth/meta/callback',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockState.role = 'owner';
  mockState.credentials = [metaStatus];
});

describe('PlatformCredentialsPanel', () => {
  it('renders nothing for roles below admin', () => {
    mockState.role = 'manager';
    const { container } = render(<PlatformCredentialsPanel />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the callback URL for registration', () => {
    render(<PlatformCredentialsPanel />);
    expect(
      screen.getByText('https://api.example/api/v1/oauth/meta/callback')
    ).toBeInTheDocument();
  });

  it('saves entered credentials', async () => {
    render(<PlatformCredentialsPanel />);
    fireEvent.change(screen.getByLabelText(/meta.*app id/i), {
      target: { value: 'cid-1' },
    });
    fireEvent.change(screen.getByLabelText(/meta.*app secret/i), {
      target: { value: 'sec-1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save meta/i }));
    await waitFor(() =>
      expect(mockState.saveMutate).toHaveBeenCalledWith({
        platform: 'meta',
        client_id: 'cid-1',
        client_secret: 'sec-1',
        developer_token: undefined,
      })
    );
  });
});
