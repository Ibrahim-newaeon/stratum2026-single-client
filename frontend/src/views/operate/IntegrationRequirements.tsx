/**
 * Integration Requirements
 *
 * What each platform needs before it can be connected — credentials, scopes,
 * and the account prerequisites that are easy to discover only after a
 * connection has already failed.
 *
 * Every value here is read off the actual implementation rather than a vendor
 * doc, so the page cannot drift from what the backend really requests:
 *   - scopes            backend/app/services/oauth/{meta,google,tiktok,snapchat}.py
 *   - credential fields backend/app/services/oauth/credentials.py (AppCredentials)
 *   - WhatsApp settings backend/app/core/config.py (whatsapp_*)
 *   - CRM clients       backend/app/services/crm/
 * If a scope changes in the provider, update it here in the same commit.
 */

import { Link } from 'react-router-dom';
import { ExternalLink, KeyRound, ShieldCheck, AlertTriangle } from 'lucide-react';

type Requirement = {
  label: string;
  detail: string;
  /** Env var or credential field the backend actually reads. */
  field?: string;
};

type Platform = {
  id: string;
  name: string;
  category: 'Ad platform' | 'Messaging' | 'CRM';
  /** How the connection is established. */
  auth: 'OAuth 2.0' | 'Access token' | 'OAuth 2.0 / API key';
  summary: string;
  requirements: Requirement[];
  /** Scopes the backend requests verbatim. */
  scopes?: string[];
  /** Things that block a connection but are not credentials. */
  prerequisites?: string[];
  docsUrl?: string;
};

const PLATFORMS: Platform[] = [
  {
    id: 'meta',
    name: 'Meta Ads',
    category: 'Ad platform',
    auth: 'OAuth 2.0',
    summary:
      'Connects Business Manager ad accounts for campaign sync, insights and Conversions API events.',
    requirements: [
      { label: 'App ID', detail: 'Meta app the OAuth dialog runs against.', field: 'META_APP_ID' },
      { label: 'App Secret', detail: 'Used for the token exchange and to verify webhook signatures.', field: 'META_APP_SECRET' },
      { label: 'Ad account IDs', detail: 'Which accounts to sync. Comma-separated.', field: 'META_AD_ACCOUNT_IDS' },
    ],
    scopes: ['ads_management', 'ads_read', 'business_management', 'pages_read_engagement'],
    prerequisites: [
      'The app must be in Live mode — Development mode returns data only for app admins.',
      'The connecting user needs an admin role on the Business Manager that owns the ad account.',
      'Advanced Access for ads_management is required before the app can serve non-admin users.',
    ],
    docsUrl: 'https://developers.facebook.com/docs/marketing-apis/get-started',
  },
  {
    id: 'google',
    name: 'Google Ads',
    category: 'Ad platform',
    auth: 'OAuth 2.0',
    summary: 'Pulls campaign structure, spend and conversion metrics from Google Ads.',
    requirements: [
      { label: 'Client ID', detail: 'From a Google Cloud OAuth 2.0 Web application credential.', field: 'GOOGLE_ADS_CLIENT_ID' },
      { label: 'Client Secret', detail: 'Paired with the client ID.', field: 'GOOGLE_ADS_CLIENT_SECRET' },
      {
        label: 'Developer token',
        detail:
          'Issued by Google Ads, separate from OAuth. Every API call fails without it — this is the field most often missed.',
        field: 'GOOGLE_ADS_DEVELOPER_TOKEN',
      },
      { label: 'Customer ID', detail: 'The 10-digit account to read, no dashes.', field: 'GOOGLE_ADS_CUSTOMER_ID' },
    ],
    scopes: ['https://www.googleapis.com/auth/adwords'],
    prerequisites: [
      'The developer token needs Basic Access or higher — a Test-Access token only reaches test accounts.',
      'If reading through a manager account, the login-customer-id must be that MCC.',
    ],
    docsUrl: 'https://developers.google.com/google-ads/api/docs/first-call/overview',
  },
  {
    id: 'tiktok',
    name: 'TikTok Ads',
    category: 'Ad platform',
    auth: 'OAuth 2.0',
    summary: 'Syncs advertiser accounts, campaigns and reporting from the Marketing API.',
    requirements: [
      { label: 'App ID', detail: 'From the TikTok for Business developer portal.', field: 'TIKTOK_APP_ID' },
      { label: 'App Secret', detail: 'Paired with the app ID for the token exchange.', field: 'TIKTOK_SECRET' },
      { label: 'Advertiser ID', detail: 'Which advertiser account to sync.', field: 'TIKTOK_ADVERTISER_ID' },
    ],
    scopes: ['advertiser.read', 'advertiser.write', 'campaign.read', 'campaign.write', 'report.read'],
    prerequisites: [
      'The app must be approved for the Marketing API — a created-but-unapproved app authorises and then returns empty advertiser lists.',
      'The redirect URI has to match the portal entry exactly, including trailing slash.',
    ],
    docsUrl: 'https://business-api.tiktok.com/portal/docs?id=1738373164380162',
  },
  {
    id: 'snapchat',
    name: 'Snapchat Ads',
    category: 'Ad platform',
    auth: 'OAuth 2.0',
    summary: 'Reads ad accounts and campaign performance from the Snap Marketing API.',
    requirements: [
      { label: 'Client ID', detail: 'From a Snap Business OAuth app.', field: 'SNAPCHAT_CLIENT_ID' },
      { label: 'Client Secret', detail: 'Paired with the client ID.', field: 'SNAPCHAT_CLIENT_SECRET' },
      { label: 'Ad account ID', detail: 'Which Snap ad account to sync.', field: 'SNAPCHAT_AD_ACCOUNT_ID' },
    ],
    scopes: ['snapchat-marketing-api'],
    prerequisites: [
      'The connecting user needs a member role on the Snap Business account.',
      'Snap issues a single coarse scope — access is governed by the role, not by scope selection.',
    ],
    docsUrl: 'https://developers.snap.com/api/marketing-api/Ads-API/introduction',
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp Business',
    category: 'Messaging',
    auth: 'Access token',
    summary:
      'Sends and receives WhatsApp messages through the Cloud API. Not an OAuth flow — credentials are configured directly.',
    requirements: [
      { label: 'Phone number ID', detail: 'The sending number registered on the Cloud API.', field: 'WHATSAPP_PHONE_NUMBER_ID' },
      { label: 'Access token', detail: 'System user token. Short-lived tokens expire in 24h — use a permanent one.', field: 'WHATSAPP_ACCESS_TOKEN' },
      { label: 'Business account ID', detail: 'The WABA that owns the number.', field: 'WHATSAPP_BUSINESS_ACCOUNT_ID' },
      {
        label: 'Verify token',
        detail:
          'A string you choose. Meta echoes it during webhook verification — required whenever a phone number ID is set.',
        field: 'WHATSAPP_VERIFY_TOKEN',
      },
      { label: 'App secret', detail: 'Validates inbound webhook signatures.', field: 'WHATSAPP_APP_SECRET' },
    ],
    prerequisites: [
      'The number must be registered on the Cloud API — an app-linked number alone is not enough.',
      'Outbound messages outside the 24-hour service window require a pre-approved template.',
    ],
    docsUrl: 'https://developers.facebook.com/docs/whatsapp/cloud-api/get-started',
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    category: 'CRM',
    auth: 'OAuth 2.0 / API key',
    summary: 'Two-way contact and company sync, with write-back of computed traits.',
    requirements: [
      { label: 'Client ID', detail: 'From a HubSpot developer app.', field: 'HUBSPOT_CLIENT_ID' },
      { label: 'Client Secret', detail: 'Paired with the client ID.', field: 'HUBSPOT_CLIENT_SECRET' },
      { label: 'API key', detail: 'Alternative to OAuth for private apps.', field: 'HUBSPOT_API_KEY' },
    ],
    prerequisites: ['Scopes must include CRM object read and write for the objects being synced.'],
    docsUrl: 'https://developers.hubspot.com/docs/api/private-apps',
  },
  {
    id: 'salesforce',
    name: 'Salesforce',
    category: 'CRM',
    auth: 'OAuth 2.0',
    summary: 'Contact and lead sync with write-back, via a Connected App.',
    requirements: [
      { label: 'Consumer key', detail: 'The Connected App client ID.' },
      { label: 'Consumer secret', detail: 'The Connected App client secret.' },
      { label: 'Instance URL', detail: 'Your org domain — sandbox and production differ.' },
    ],
    prerequisites: ['API access must be enabled on the user profile; it is off by default on some editions.'],
    docsUrl: 'https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_oauth_and_connected_apps.htm',
  },
  {
    id: 'zoho',
    name: 'Zoho CRM',
    category: 'CRM',
    auth: 'OAuth 2.0',
    summary: 'Contact synchronisation and write-back against Zoho CRM modules.',
    requirements: [
      { label: 'Client ID', detail: 'From the Zoho API console.' },
      { label: 'Client Secret', detail: 'Paired with the client ID.' },
      { label: 'Data centre', detail: 'Zoho is region-scoped — .com, .eu and .in are different hosts.' },
    ],
    prerequisites: ['Tokens issued in one data centre are rejected by the others.'],
    docsUrl: 'https://www.zoho.com/crm/developer/docs/api/v3/oauth-overview.html',
  },
  {
    id: 'pipedrive',
    name: 'Pipedrive',
    category: 'CRM',
    auth: 'OAuth 2.0 / API key',
    summary: 'Deal and person sync with write-back.',
    requirements: [
      { label: 'Client ID', detail: 'From a Pipedrive app.' },
      { label: 'Client Secret', detail: 'Paired with the client ID.' },
      { label: 'API token', detail: 'Alternative to OAuth for a single account.' },
    ],
    docsUrl: 'https://developers.pipedrive.com/docs/api/v1',
  },
];

const CATEGORIES = ['Ad platform', 'Messaging', 'CRM'] as const;

function PlatformCard({ platform }: { platform: Platform }) {
  return (
    <article className="rounded-2xl border border-border bg-card p-6 flex flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-semibold text-foreground">{platform.name}</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-prose">{platform.summary}</p>
        </div>
        <span className="font-mono text-[0.7rem] uppercase tracking-wider px-2.5 py-1 rounded-full border border-border text-muted-foreground whitespace-nowrap">
          {platform.auth}
        </span>
      </header>

      <section>
        <h4 className="flex items-center gap-2 font-mono text-[0.7rem] uppercase tracking-wider text-muted-foreground mb-3">
          <KeyRound className="w-3.5 h-3.5" aria-hidden="true" />
          Credentials
        </h4>
        <dl className="flex flex-col gap-2.5">
          {platform.requirements.map((r) => (
            <div key={r.label} className="flex flex-col sm:flex-row sm:gap-3">
              <dt className="text-sm font-medium text-foreground sm:w-44 sm:flex-shrink-0">{r.label}</dt>
              <dd className="text-sm text-muted-foreground">
                {r.detail}
                {r.field && (
                  <code className="ml-2 font-mono text-xs px-1.5 py-0.5 rounded bg-muted text-foreground/80">
                    {r.field}
                  </code>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {platform.scopes && (
        <section>
          <h4 className="flex items-center gap-2 font-mono text-[0.7rem] uppercase tracking-wider text-muted-foreground mb-2">
            <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
            Scopes requested
          </h4>
          <ul className="flex flex-wrap gap-1.5">
            {platform.scopes.map((s) => (
              <li
                key={s}
                className="font-mono text-xs px-2 py-1 rounded-md bg-muted text-foreground/80 break-all"
              >
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      {platform.prerequisites && (
        <section>
          <h4 className="flex items-center gap-2 font-mono text-[0.7rem] uppercase tracking-wider text-muted-foreground mb-2">
            <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
            Before you connect
          </h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-5">
            {platform.prerequisites.map((p) => (
              <li key={p} className="text-sm text-muted-foreground marker:text-border">
                {p}
              </li>
            ))}
          </ul>
        </section>
      )}

      {platform.docsUrl && (
        <a
          href={platform.docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline underline-offset-4 w-fit"
        >
          Provider setup guide
          <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
        </a>
      )}
    </article>
  );
}

export default function IntegrationRequirements() {
  return (
    <div className="flex flex-col gap-8 pb-12">
      <header className="flex flex-col gap-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          Integration requirements
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          What each platform needs before it can be connected. Scopes and credential
          fields match what the backend actually requests, so this is the list to
          gather against — not the vendor marketing page.
        </p>
        <Link
          to="/dashboard/settings/integrations"
          className="text-sm font-medium text-primary hover:underline underline-offset-4 w-fit"
        >
          Go to Integrations to connect an account →
        </Link>
      </header>

      {CATEGORIES.map((category) => {
        const items = PLATFORMS.filter((p) => p.category === category);
        if (items.length === 0) return null;
        return (
          <section key={category} className="flex flex-col gap-4">
            <h2 className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground flex items-center gap-3">
              {category}
              <span className="h-px flex-1 bg-border" aria-hidden="true" />
            </h2>
            <div className="grid gap-4 xl:grid-cols-2">
              {items.map((p) => (
                <PlatformCard key={p.id} platform={p} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
