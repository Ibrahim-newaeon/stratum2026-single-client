/**
 * Shared Left Panel for Authentication pages
 * ADs Growth System figma theme — ink surface, ember accent, Geist typography
 */

import { cn } from '@/lib/utils';

interface AuthLeftPanelProps {
  className?: string;
}

export default function AuthLeftPanel({ className }: AuthLeftPanelProps) {
  return (
    <section
      className={cn(
        'hidden lg:flex w-2/5 bg-[#0D0C13] relative flex-col justify-between p-12 border-r border-[#282531] overflow-hidden',
        className
      )}
      style={{ fontFamily: 'Geist, system-ui, sans-serif' }}
    >
      {/* Side ember glow */}
      <div
        className="absolute inset-0 pointer-events-none opacity-70"
        style={{
          background:
            'radial-gradient(70% 60% at 0% 50%, rgba(255,90,31,0.18) 0%, rgba(255,90,31,0.04) 45%, transparent 75%)',
          filter: 'blur(40px)',
        }}
        aria-hidden="true"
      />

      {/* Top: logo + back-home (plain <a> for full page load → figma landing) */}
      <div className="relative z-10 flex items-center justify-between">
        <a href="/landing.html" className="flex items-center gap-2" aria-label="ADs Growth System home">
          <span className="text-[19px] font-medium tracking-tight text-white">
            ADs Growth <span className="text-primary">System</span>
          </span>
        </a>
        <a
          href="/landing.html"
          className="text-[12px] text-[#A9A6BD] hover:text-white transition-colors flex items-center gap-1"
        >
          ← Back to site
        </a>
      </div>

      {/* Center: testimonial */}
      <div className="relative z-10 max-w-md">
        <span
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11.5px] uppercase tracking-[0.06em] font-medium text-[#ECECEC] mb-6"
          style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid #282531',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full bg-[#29D6C7]"
            style={{ boxShadow: '0 0 8px #29D6C7' }}
          />
          Trusted by 500+ growth teams
        </span>
        <blockquote className="text-[28px] leading-tight tracking-tight text-white mt-6 mb-8">
          &ldquo;ADs Growth System doesn't just manage our ads. It partners with us to grow revenue — with
          every decision auditable and reversible.&rdquo;
        </blockquote>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#282531] flex items-center justify-center text-[#A9A6BD] text-sm font-medium">
            JD
          </div>
          <div>
            <p className="text-sm font-medium text-white">Jane Doe</p>
            <p className="text-xs text-[#7B7791]">CMO, GrowthCo</p>
          </div>
        </div>
      </div>

      {/* Bottom: status marker */}
      <div
        className="relative z-10 flex items-center gap-2 text-[11px] text-[#7B7791] uppercase tracking-[0.12em]"
        style={{ fontFamily: 'Geist Mono, monospace' }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-[#29D6C7]" />
        Trust engine — operational
      </div>
    </section>
  );
}
