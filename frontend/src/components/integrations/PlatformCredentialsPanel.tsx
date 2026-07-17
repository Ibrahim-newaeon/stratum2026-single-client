/**
 * Owner/admin panel: per-deployment OAuth app credentials for ad platforms.
 *
 * Black-box model: each customer registers their own developer app per
 * platform and pastes its credentials here (encrypted at rest server-side;
 * secrets are write-only). The callback URL shown per platform must be
 * registered in that platform's developer console.
 */

import { useState } from 'react';
import { AlertTriangle, Copy, KeyRound, Trash2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import {
  AppCredentialStatus,
  useAppCredentials,
  useDeleteAppCredentials,
  useSaveAppCredentials,
} from '@/api/appCredentials';
import type { AdPlatform } from '@/api/connections';
import { getApiErrorMessage } from '@/api/client';
import { Card } from '@/components/primitives/Card';
import { useToast } from '@/components/ui/use-toast';

const PLATFORM_META: Record<
  AdPlatform,
  { label: string; idLabel: string; secretLabel: string; hasDevToken: boolean }
> = {
  meta: { label: 'Meta', idLabel: 'App ID', secretLabel: 'App secret', hasDevToken: false },
  google: { label: 'Google Ads', idLabel: 'Client ID', secretLabel: 'Client secret', hasDevToken: true },
  tiktok: { label: 'TikTok', idLabel: 'App ID', secretLabel: 'App secret', hasDevToken: false },
  snapchat: { label: 'Snapchat', idLabel: 'Client ID', secretLabel: 'Client secret', hasDevToken: false },
};

function CredentialCard({ status }: { status: AppCredentialStatus }) {
  const meta = PLATFORM_META[status.platform];
  const { toast } = useToast();
  const save = useSaveAppCredentials();
  const remove = useDeleteAppCredentials();
  const [clientId, setClientId] = useState(status.client_id ?? '');
  const [clientSecret, setClientSecret] = useState('');
  const [developerToken, setDeveloperToken] = useState('');
  const [copied, setCopied] = useState(false);

  const sourceLabel =
    status.source === 'database'
      ? 'Configured'
      : status.source === 'environment'
        ? 'Configured via server environment'
        : 'Not configured';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(status.callback_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleSave = async () => {
    try {
      await save.mutateAsync({
        platform: status.platform,
        client_id: clientId.trim(),
        client_secret: clientSecret.trim() || undefined,
        developer_token: meta.hasDevToken
          ? developerToken.trim() || undefined
          : undefined,
      });
      setClientSecret('');
      setDeveloperToken('');
      toast({ title: `${meta.label} credentials saved` });
    } catch (error) {
      toast({
        title: `Couldn't save ${meta.label} credentials`,
        description: getApiErrorMessage(error),
        variant: 'destructive',
      });
    }
  };

  const handleRemove = async () => {
    try {
      await remove.mutateAsync(status.platform);
      toast({ title: `${meta.label} credentials removed` });
    } catch (error) {
      toast({
        title: `Couldn't remove ${meta.label} credentials`,
        description: getApiErrorMessage(error),
        variant: 'destructive',
      });
    }
  };

  const idInputId = `${status.platform}-client-id`;
  const secretInputId = `${status.platform}-client-secret`;
  const devInputId = `${status.platform}-developer-token`;

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-foreground">{meta.label}</h3>
        <span className="text-xs text-muted-foreground">{sourceLabel}</span>
      </div>

      <div className="space-y-3">
        <div>
          <label htmlFor={idInputId} className="block text-xs text-muted-foreground mb-1">
            {meta.label} {meta.idLabel}
          </label>
          <input
            id={idInputId}
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            autoComplete="off"
          />
        </div>
        <div>
          <label htmlFor={secretInputId} className="block text-xs text-muted-foreground mb-1">
            {meta.label} {meta.secretLabel}
          </label>
          <input
            id={secretInputId}
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder={status.source === 'database' ? '••••••• saved' : ''}
            className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            autoComplete="new-password"
          />
        </div>
        {meta.hasDevToken && (
          <div>
            <label htmlFor={devInputId} className="block text-xs text-muted-foreground mb-1">
              Developer token
            </label>
            <input
              id={devInputId}
              type="password"
              value={developerToken}
              onChange={(e) => setDeveloperToken(e.target.value)}
              placeholder={status.has_developer_token ? '••••••• saved' : ''}
              className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
              autoComplete="new-password"
            />
          </div>
        )}
        {meta.hasDevToken && status.configured && !status.has_developer_token && (
          <p className="flex items-center gap-1.5 text-xs text-warning">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            No developer token — Google Ads API calls will fail until one is
            added.
          </p>
        )}
      </div>

      <div className="rounded-xl bg-muted px-3 py-2">
        <p className="text-[11px] text-muted-foreground mb-1">
          Register this callback URL in your {meta.label} developer app:
        </p>
        <div className="flex items-center gap-2">
          <code className="text-xs text-foreground break-all flex-1">
            {status.callback_url}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label={`Copy ${meta.label} callback URL`}
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          {copied && <span className="text-xs text-primary">Copied</span>}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={save.isPending || !clientId.trim()}
          className="rounded-full px-4 py-1.5 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          Save {meta.label}
        </button>
        {status.source === 'database' && (
          <button
            type="button"
            onClick={handleRemove}
            disabled={remove.isPending}
            className="rounded-full px-3 py-1.5 text-sm text-muted-foreground hover:text-destructive inline-flex items-center gap-1"
          >
            <Trash2 className="w-3.5 h-3.5" /> Remove
          </button>
        )}
      </div>
      {status.source === 'database' && (
        <p className="text-[11px] text-muted-foreground">
          Removing stored credentials does not disconnect already-connected
          accounts.
        </p>
      )}
    </Card>
  );
}

export function PlatformCredentialsPanel() {
  const { user } = useAuth();
  const { credentials, isLoading, isError } = useAppCredentials(
    user?.role === 'owner' || user?.role === 'admin'
  );

  if (user?.role !== 'owner' && user?.role !== 'admin') return null;
  if (isLoading || isError || credentials.length === 0) return null;

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-primary" />
          Platform app credentials
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          One-time setup per platform: create a developer app on the platform,
          register the callback URL below, then paste its credentials here.
          Stored encrypted; secrets are never shown again.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {credentials.map((c) => (
          <CredentialCard key={c.platform} status={c} />
        ))}
      </div>
    </section>
  );
}
