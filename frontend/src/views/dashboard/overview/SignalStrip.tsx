/**
 * SignalStrip — alert-summary chips + bulk-acknowledge action.
 *
 * Three chips: 🔴 trust holds  ·  🟡 signal/pacing  ·  🔵 autopilot pending
 * Clicking a chip drives the FocusPane (selected-alert routing).
 *
 * If alerts = 0, the strip collapses to a single "All clear" chip in
 * a hairline-only treatment so the home doesn't feel empty.
 *
 * "Acknowledge" is intentionally NOT one-click destructive — it opens a
 * preview drawer (out of scope for this commit; the button currently
 * defers to an onAcknowledgeAll handler the parent owns).
 */

import { CheckCircle2, Bell } from 'lucide-react';
import { Card } from '@/components/primitives/Card';
import { StatusPill } from '@/components/primitives/StatusPill';
import { cn } from '@/lib/utils';
import type { AlertSummary, FocusKey } from './types';

interface SignalStripProps {
  summaries: AlertSummary[];
  selectedFocus: FocusKey;
  onSelectFocus: (focus: FocusKey) => void;
  onAcknowledgeAll?: () => void;
  loading?: boolean;
}

const SEVERITY_VARIANT = {
  critical: 'unhealthy' as const,
  warning: 'degraded' as const,
  info: 'neutral' as const,
};

function ChipButton({
  active,
  onClick,
  children,
  className,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-full transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
        active
          ? 'ring-2 ring-primary/50 ring-offset-2 ring-offset-card'
          : 'opacity-80 hover:opacity-100',
        className
      )}
    >
      {children}
    </button>
  );
}

export function SignalStrip({
  summaries,
  selectedFocus,
  onSelectFocus,
  onAcknowledgeAll,
  loading,
}: SignalStripProps) {
  const totalCount = summaries.reduce((sum, s) => sum + s.count, 0);
  const allClear = !loading && totalCount === 0;

  if (allClear) {
    return (
      <Card className="px-5 py-3 flex items-center gap-3">
        <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <p className="text-body font-medium text-foreground">All clear.</p>
          <p className="text-meta text-muted-foreground">
            No alerts require attention. Trust gate operational; autopilot running.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="px-5 py-3.5 flex items-center gap-3 flex-wrap">
      {/* Bell in a sunken clay well — anchors the strip visually */}
      <span
        aria-hidden="true"
        className={cn(
          'flex-shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full clay-inset',
          totalCount > 0 ? 'bg-primary/10 text-primary' : 'bg-muted/40 text-muted-foreground'
        )}
      >
        <Bell className="w-4 h-4" />
      </span>

      <div className="flex flex-wrap items-center gap-2 min-w-0">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-7 w-28 rounded-full bg-muted/50 animate-pulse"
                aria-hidden="true"
              />
            ))
          : summaries.map((s) => (
              <ChipButton
                key={s.focus}
                active={s.focus === selectedFocus}
                onClick={() => onSelectFocus(s.focus)}
              >
                <StatusPill
                  variant={SEVERITY_VARIANT[s.severity]}
                  size="md"
                  pulse={s.severity === 'critical'}
                >
                  <span className="tabular-nums font-semibold text-[13px]">{s.count}</span>
                  <span className="ml-1.5 normal-case tracking-normal font-medium">{s.label}</span>
                </StatusPill>
              </ChipButton>
            ))}
      </div>

      {onAcknowledgeAll && totalCount > 0 && !loading && (
        <button
          type="button"
          onClick={onAcknowledgeAll}
          className={cn(
            'ml-auto flex-shrink-0 inline-flex items-center gap-1.5 px-4 py-2 rounded-full',
            'text-meta font-semibold whitespace-nowrap border border-primary/30',
            'bg-primary/15 text-primary clay-raised-sm clay-pressable text-embossed',
            'hover:bg-primary/25 hover:border-primary/45 transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
          )}
        >
          <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
          Acknowledge all
        </button>
      )}
    </Card>
  );
}

export default SignalStrip;
