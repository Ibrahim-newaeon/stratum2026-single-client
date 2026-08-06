/**
 * IntegrationsHub — standalone /dashboard/integrations page.
 *
 * All ad/messaging platforms in one place. Selecting a platform reveals the
 * full credential form (field specs come from the backend registry, so the
 * UI never drifts from what the API accepts), with Save → Test connection.
 * Meta and WhatsApp are the featured "start here" integrations; OAuth
 * platforms additionally expose the Connect flow + callback URL.
 */

import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import {
  CheckCircle2,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  PlugZap,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import { Card } from '@/components/primitives/Card';
import { StatusPill } from '@/components/primitives/StatusPill';
import {
  useConnections,
  startOAuthConnect,
  type AdPlatform,
} from '@/api/connections';
import {
  usePlatformCredentials,
  useSaveCredentials,
  useTestConnection,
  type ConnectionTestResult,
  type CredentialStatus,
} from '@/api/platformCredentials';
import { getApiErrorMessage } from '@/api/client';
import { cn } from '@/lib/utils';

/** Display order — featured first. */
const PLATFORM_ORDER = ['meta', 'whatsapp', 'google', 'tiktok', 'snapchat'];
const FEATURED = new Set(['meta', 'whatsapp']);

/** Brand tile colors (external brand identities, not theme tokens). */
const BRAND: Record<string, { bg: string; letter: string }> = {
  meta: { bg: '#0866FF', letter: 'M' },
  whatsapp: { bg: '#25D366', letter: 'W' },
  google: { bg: '#4285F4', letter: 'G' },
  tiktok: { bg: '#00F2EA', letter: 'T' },
  snapchat: { bg: '#FFFC00', letter: 'S' },
};

function BrandTile({ platform }: { platform: string }) {
  const b = BRAND[platform] ?? { bg: 'hsl(var(--muted))', letter: '?' };
  return (
    <span
      aria-hidden="true"
      className="inline-flex items-center justify-center w-10 h-10 rounded-xl clay-raised-sm font-display font-bold text-lg"
      style={{ backgroundColor: b.bg, color: platform === 'snapchat' || platform === 'tiktok' ? '#111' : '#fff' }}
    >
      {b.letter}
    </span>
  );
}

function TestResultBanner({ result }: { result: ConnectionTestResult }) {
  const tone =
    result.status === 'valid'
      ? 'text-success bg-success/15 border-success/40'
      : result.status === 'configured_unverified'
        ? 'text-warning bg-warning/15 border-warning/40'
        : 'text-danger bg-danger/15 border-danger/40';
  const Icon = result.ok ? CheckCircle2 : XCircle;
  const meta = result.metadata ?? {};
  return (
    <div className={cn('flex items-start gap-2.5 rounded-2xl border px-4 py-3 clay-inset', tone)} role="status">
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" aria-hidden="true" />
      <div className="min-w-0 text-body-sm">
        <p className="font-medium">{result.detail}</p>
        {'display_phone_number' in meta && (
          <p className="text-meta mt-1 opacity-80">
            {String(meta.verified_name ?? '')} · {String(meta.display_phone_number ?? '')}
            {meta.quality_rating ? ` · quality: ${String(meta.quality_rating)}` : ''}
          </p>
        )}
      </div>
    </div>
  );
}

function CredentialForm({ status }: { status: CredentialStatus }) {
  const save = useSaveCredentials();
  const test = useTestConnection();
  const [values, setValues] = useState<Record<string, string>>({});
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const setField = (key: string, v: string) => {
    setValues((prev) => ({ ...prev, [key]: v }));
    setFormError(null);
  };

  const fieldSaved = (key: string, maps_to: string): boolean => {
    if (maps_to === 'client_id') return !!status.client_id;
    if (maps_to === 'client_secret') return status.configured;
    if (maps_to === 'developer_token') return status.has_developer_token;
    return status.extra_configured.includes(key);
  };

  const handleSave = async () => {
    const clientIdSpec = status.fields.find((f) => f.maps_to === 'client_id');
    const clientId = (values[clientIdSpec?.key ?? 'client_id'] ?? '').trim() || status.client_id || '';
    if (!clientId) {
      setFormError(`${clientIdSpec?.label ?? 'ID'} is required.`);
      return;
    }
    // First-time save requires every required field to be present.
    if (!status.configured) {
      const missing = status.fields
        .filter((f) => f.required && !(values[f.key] ?? '').trim())
        .filter((f) => f.maps_to !== 'client_id')
        .map((f) => f.label);
      if (missing.length) {
        setFormError(`Required: ${missing.join(', ')}`);
        return;
      }
    }
    const extra: Record<string, string> = {};
    for (const f of status.fields) {
      if (f.maps_to === 'extra' && values[f.key] !== undefined) {
        extra[f.key] = values[f.key].trim();
      }
    }
    const secretSpec = status.fields.find((f) => f.maps_to === 'client_secret');
    const devSpec = status.fields.find((f) => f.maps_to === 'developer_token');
    try {
      await save.mutateAsync({
        platform: status.platform,
        payload: {
          client_id: clientId,
          client_secret: (secretSpec && values[secretSpec.key]?.trim()) || undefined,
          developer_token: (devSpec && values[devSpec.key]?.trim()) || undefined,
          extra: Object.keys(extra).length ? extra : undefined,
        },
      });
      test.reset();
    } catch (e) {
      setFormError(getApiErrorMessage(e));
    }
  };

  const handleConnect = async () => {
    try {
      const url = await startOAuthConnect(status.platform as AdPlatform, '/dashboard/integrations');
      if (url) window.location.assign(url);
      else setFormError('No authorization URL returned — save valid app credentials first.');
    } catch (e) {
      setFormError(getApiErrorMessage(e));
    }
  };

  const copyCallback = async () => {
    try {
      await navigator.clipboard.writeText(status.callback_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="space-y-4">
      {status.fields.map((f) => {
        const saved = fieldSaved(f.key, f.maps_to);
        const show = !!showSecret[f.key];
        return (
          <div key={f.key}>
            <label
              htmlFor={`cred-${status.platform}-${f.key}`}
              className="block text-meta font-mono uppercase tracking-[0.06em] text-muted-foreground text-debossed mb-1.5"
            >
              {f.label}
              {f.required && <span className="text-danger ml-1">*</span>}
              {saved && (
                <span className="ml-2 normal-case tracking-normal text-success">saved ✓</span>
              )}
            </label>
            <div className="relative">
              <input
                id={`cred-${status.platform}-${f.key}`}
                type={f.secret && !show ? 'password' : 'text'}
                autoComplete="off"
                value={
                  values[f.key] ??
                  (f.maps_to === 'client_id' ? (status.client_id ?? '') : '')
                }
                onChange={(e) => setField(f.key, e.target.value)}
                placeholder={
                  saved && f.secret ? '•••••••• (saved — leave blank to keep)' : f.help || f.label
                }
                className={cn(
                  'w-full px-4 py-2.5 rounded-xl bg-background/60 clay-inset',
                  'border border-border/60 text-foreground text-body-sm',
                  'placeholder:text-muted-foreground/60',
                  'focus:outline-none focus:ring-2 focus:ring-ring focus:border-primary/50',
                  f.secret && 'pr-11 font-mono'
                )}
              />
              {f.secret && (
                <button
                  type="button"
                  onClick={() => setShowSecret((p) => ({ ...p, [f.key]: !show }))}
                  aria-label={show ? `Hide ${f.label}` : `Show ${f.label}`}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              )}
            </div>
            {f.help && <p className="text-meta text-muted-foreground mt-1">{f.help}</p>}
          </div>
        );
      })}

      {/* Callback / webhook URL — needed inside the platform's own console */}
      <div className="rounded-xl bg-muted/40 clay-inset px-4 py-3">
        <p className="text-meta font-mono uppercase tracking-[0.06em] text-muted-foreground mb-1">
          {status.oauth ? 'OAuth callback URL' : 'Webhook verification URL'}
        </p>
        <div className="flex items-center gap-2">
          <code className="text-body-sm text-foreground truncate flex-1">{status.callback_url}</code>
          <button
            type="button"
            onClick={copyCallback}
            aria-label="Copy URL"
            className="flex-shrink-0 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            {copied ? <CheckCircle2 className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {formError && (
        <p className="text-body-sm text-danger" role="alert">
          {formError}
        </p>
      )}
      {save.isSuccess && !save.isPending && !formError && (
        <p className="text-body-sm text-success" role="status">
          Credentials saved.
        </p>
      )}
      {test.data && <TestResultBanner result={test.data} />}
      {test.isError && (
        <p className="text-body-sm text-danger" role="alert">
          {getApiErrorMessage(test.error)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2.5 pt-1">
        <button
          type="button"
          onClick={handleSave}
          disabled={save.isPending}
          className={cn(
            'inline-flex items-center gap-1.5 px-5 py-2 rounded-full',
            'bg-primary text-primary-foreground text-meta font-semibold text-embossed',
            'clay-raised-sm clay-pressable hover:brightness-110 transition-all',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
          )}
        >
          {save.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />}
          Save credentials
        </button>
        <button
          type="button"
          onClick={() => test.mutate(status.platform)}
          disabled={test.isPending}
          className={cn(
            'inline-flex items-center gap-1.5 px-5 py-2 rounded-full',
            'bg-secondary/15 text-secondary border border-secondary/35 text-meta font-semibold',
            'clay-raised-sm clay-pressable hover:bg-secondary/25 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
          )}
        >
          {test.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <PlugZap className="w-3.5 h-3.5" aria-hidden="true" />
          )}
          Test connection
        </button>
        {status.oauth && (
          <button
            type="button"
            onClick={handleConnect}
            className={cn(
              'inline-flex items-center gap-1.5 px-5 py-2 rounded-full',
              'bg-card text-foreground border border-border text-meta font-semibold',
              'clay-raised-sm clay-pressable hover:bg-muted transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
            )}
          >
            <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            Connect via OAuth
          </button>
        )}
      </div>
    </div>
  );
}

export default function IntegrationsHub() {
  const [searchParams, setSearchParams] = useSearchParams();
  const credentials = usePlatformCredentials();
  const { connections } = useConnections();

  const ordered = useMemo(() => {
    const byPlatform = new Map((credentials.data ?? []).map((c) => [c.platform, c]));
    return PLATFORM_ORDER.map((p) => byPlatform.get(p)).filter(Boolean) as CredentialStatus[];
  }, [credentials.data]);

  const requested = searchParams.get('platform');
  const selected =
    ordered.find((c) => c.platform === requested)?.platform ?? ordered[0]?.platform ?? null;
  const selectedStatus = ordered.find((c) => c.platform === selected) ?? null;

  const oauthState = (platform: string) =>
    connections.find((c) => c.platform === platform)?.status ?? null;

  const forbidden =
    credentials.isError && String(getApiErrorMessage(credentials.error)).length > 0;

  return (
    <>
      <Helmet>
        <title>Integrations · ADs Growth System</title>
      </Helmet>

      <div className="space-y-6">
        <header>
          <h1 className="text-h1 font-medium tracking-tight text-foreground text-embossed">
            Integrations
          </h1>
          <p className="text-body text-muted-foreground mt-1">
            Connect your ad and messaging platforms. Start with Meta and WhatsApp, then
            test each connection before turning on automations.
          </p>
        </header>

        {credentials.isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-20 rounded-2xl bg-muted/50 animate-pulse" />
              ))}
            </div>
            <div className="h-96 rounded-2xl bg-muted/40 animate-pulse" />
          </div>
        ) : credentials.isError ? (
          <Card className="p-6">
            <p className="text-body text-danger">
              {forbidden
                ? getApiErrorMessage(credentials.error)
                : 'Could not load integrations.'}
            </p>
            <p className="text-body-sm text-muted-foreground mt-2">
              Managing platform credentials requires an owner or admin role.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5 items-start">
            {/* Platform list */}
            <nav aria-label="Platforms" className="space-y-3">
              {ordered.map((c) => {
                const oauth = oauthState(c.platform);
                const active = c.platform === selected;
                return (
                  <button
                    key={c.platform}
                    type="button"
                    onClick={() => {
                      const next = new URLSearchParams(searchParams);
                      next.set('platform', c.platform);
                      setSearchParams(next, { replace: true });
                    }}
                    aria-pressed={active}
                    className={cn(
                      'w-full text-left rounded-2xl border p-4 clay-pressable transition-colors',
                      active
                        ? 'bg-card border-primary/45 clay-raised ring-2 ring-primary/30'
                        : 'bg-card/60 border-border/60 clay-raised-sm hover:border-secondary/40'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <BrandTile platform={c.platform} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-body font-medium text-foreground truncate">
                            {c.label}
                          </span>
                          {FEATURED.has(c.platform) && (
                            <span className="text-[10px] font-mono uppercase tracking-[0.06em] px-1.5 py-0.5 rounded-full bg-secondary/20 text-secondary clay-raised-sm">
                              Start here
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          <StatusPill
                            variant={c.configured ? 'healthy' : 'neutral'}
                            size="sm"
                          >
                            {c.configured
                              ? c.source === 'database'
                                ? 'Credentials saved'
                                : 'Configured via env'
                              : 'Not configured'}
                          </StatusPill>
                          {c.oauth && oauth === 'connected' && (
                            <StatusPill variant="healthy" size="sm" pulse>
                              OAuth connected
                            </StatusPill>
                          )}
                          {c.oauth && oauth === 'expired' && (
                            <StatusPill variant="degraded" size="sm">
                              Token expired
                            </StatusPill>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </nav>

            {/* Detail form */}
            {selectedStatus && (
              <Card variant="elevated" className="p-6">
                <div className="flex items-center gap-3 mb-1">
                  <BrandTile platform={selectedStatus.platform} />
                  <div>
                    <h2 className="text-h2 font-medium text-foreground text-embossed">
                      {selectedStatus.label}
                    </h2>
                    <p className="text-meta text-muted-foreground flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                      Secrets are encrypted at rest and never shown again after saving.
                    </p>
                  </div>
                </div>
                <div className="divider-gradient my-4" />
                <CredentialForm key={selectedStatus.platform} status={selectedStatus} />
              </Card>
            )}
          </div>
        )}
      </div>
    </>
  );
}
