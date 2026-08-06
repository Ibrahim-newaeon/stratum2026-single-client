/**
 * IntegrationsHub — platform list, field-spec rendering, and test-connection
 * surface. API modules are mocked; specs mirror the backend registry shape.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';

import IntegrationsHub from './IntegrationsHub';
import type { CredentialStatus } from '@/api/platformCredentials';

const mkStatus = (over: Partial<CredentialStatus>): CredentialStatus => ({
  platform: 'meta',
  label: 'Meta',
  configured: false,
  source: null,
  client_id: null,
  has_developer_token: false,
  callback_url: 'http://localhost:8000/api/v1/oauth/meta/callback',
  oauth: true,
  fields: [
    { key: 'client_id', label: 'App ID', required: true, secret: false, maps_to: 'client_id', help: '' },
    { key: 'client_secret', label: 'App Secret', required: true, secret: true, maps_to: 'client_secret', help: '' },
  ],
  extra_configured: [],
  ...over,
});

const statuses: CredentialStatus[] = [
  mkStatus({}),
  mkStatus({
    platform: 'whatsapp',
    label: 'WhatsApp Business',
    oauth: false,
    callback_url: 'http://localhost:8000/api/v1/whatsapp/webhooks/verify',
    fields: [
      { key: 'client_id', label: 'Phone Number ID', required: true, secret: false, maps_to: 'client_id', help: '' },
      { key: 'client_secret', label: 'Access Token', required: true, secret: true, maps_to: 'client_secret', help: '' },
      { key: 'developer_token', label: 'Business Account ID (WABA)', required: true, secret: false, maps_to: 'developer_token', help: '' },
      { key: 'app_secret', label: 'App Secret', required: false, secret: true, maps_to: 'extra', help: '' },
      { key: 'verify_token', label: 'Webhook Verify Token', required: false, secret: true, maps_to: 'extra', help: '' },
    ],
  }),
  mkStatus({ platform: 'google', label: 'Google Ads' }),
  mkStatus({ platform: 'tiktok', label: 'TikTok' }),
  mkStatus({ platform: 'snapchat', label: 'Snapchat' }),
];

const testMutate = vi.fn();

vi.mock('@/api/platformCredentials', () => ({
  usePlatformCredentials: () => ({ data: statuses, isLoading: false, isError: false }),
  useSaveCredentials: () => ({ mutateAsync: vi.fn(), isPending: false, isSuccess: false, reset: vi.fn() }),
  useTestConnection: () => ({
    mutate: testMutate,
    isPending: false,
    data: undefined,
    isError: false,
    reset: vi.fn(),
  }),
}));

vi.mock('@/api/connections', () => ({
  useConnections: () => ({ connections: [] }),
  startOAuthConnect: vi.fn(),
}));

function renderPage(initialEntry = '/dashboard/integrations') {
  return render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <IntegrationsHub />
      </MemoryRouter>
    </HelmetProvider>
  );
}

describe('IntegrationsHub', () => {
  it('lists all platforms with Meta and WhatsApp featured', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Integrations' })).toBeInTheDocument();
    for (const label of ['Meta', 'WhatsApp Business', 'Google Ads', 'TikTok', 'Snapchat']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText('Start here')).toHaveLength(2);
  });

  it('selects a platform and renders its full field spec', () => {
    renderPage('/dashboard/integrations?platform=whatsapp');
    const input = { selector: 'input' } as const;
    expect(screen.getByLabelText(/Phone Number ID/, input)).toBeInTheDocument();
    expect(screen.getByLabelText(/Access Token/, input)).toBeInTheDocument();
    expect(screen.getByLabelText(/Business Account ID/, input)).toBeInTheDocument();
    expect(screen.getByLabelText(/App Secret/, input)).toBeInTheDocument();
    expect(screen.getByLabelText(/Webhook Verify Token/, input)).toBeInTheDocument();
    // Direct-API platform surfaces the webhook URL, not an OAuth callback
    expect(screen.getByText(/Webhook verification URL/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Connect via OAuth/ })).not.toBeInTheDocument();
  });

  it('fires the connection test for the selected platform', () => {
    renderPage('/dashboard/integrations?platform=whatsapp');
    fireEvent.click(screen.getByRole('button', { name: /Test connection/ }));
    expect(testMutate).toHaveBeenCalledWith('whatsapp');
  });

  it('shows the OAuth connect button for OAuth platforms', () => {
    renderPage('/dashboard/integrations?platform=meta');
    expect(screen.getByRole('button', { name: /Connect via OAuth/ })).toBeInTheDocument();
    expect(screen.getByText(/OAuth callback URL/)).toBeInTheDocument();
  });
});
