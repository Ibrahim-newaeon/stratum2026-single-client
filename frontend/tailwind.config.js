/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1224px', // XML <content-width default="1224px"> (was 1400px)
      },
    },
    extend: {
      screens: {
        // XML <breakpoints mobile-max="920px"> — additive; Tailwind defaults untouched
        desktop: '921px',
      },
      colors: {
        // Semantic tokens (resolved per theme via CSS vars in index.css)
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },

        // Brand scale — Opal gold ramp (replaces the ember stratum-50…950).
        // 50–500 anchor directly on XML swatches; 600–950 are derived shades
        // (no darker golds exist in the XML) kept so existing stratum-N
        // utilities keep resolving.
        stratum: {
          50: '#FFFCF3', // logo card-background cream
          100: '#F5F5DC', // cream (verified palette)
          200: '#EFDFBC', // cream-2 (extended strip)
          300: '#C2A670', // palette gold (verified)
          400: '#C1A15A', // strip gold
          500: '#BB8B41', // live-site / deployed UI gold
          600: '#9A7335', // derived
          700: '#7A5B2A', // derived
          800: '#5B441F', // derived
          900: '#3D2D15', // derived
          950: '#241A0C', // derived
        },

        // XML gold-family — all four documented golds, by XML id
        gold: {
          DEFAULT: '#BB8B41', // live-site
          logo: '#BD8C41', // figma logo master (pixel-sampled)
          palette: '#C2A670', // figma palette board (verified)
          strip: '#C1A15A', // brand-guide extended strip
        },

        // XML brand palette — verified primary board + extended strip
        charcoal: '#2C2C2C',
        cream: {
          DEFAULT: '#F5F5DC', // verified palette
          2: '#EFDFBC', // extended strip cream-2
          card: '#FFFCF3', // logo card-background
        },
        burgundy: '#800020',
        'slate-blue': '#394E6C',
        navy: '#000C66', // extended strip
        'olive-sage': '#485342', // live-site secondary text — NOT in brand guide (flagged)

        // Named dark-surface tokens (kept hard-coded for static landing/auth html parity)
        ink: '#000000', // reversed-logo background (was #0B0B0B)
        surface: {
          DEFAULT: '#1A1A1A', // was #141414
          tier2: '#2C2C2C', // was #1A1A1A
          // Theme-aware surface tiers
          primary: 'hsl(var(--surface-primary))',
          secondary: 'hsl(var(--surface-secondary))',
          tertiary: 'hsl(var(--surface-tertiary))',
          elevated: 'hsl(var(--surface-elevated))',
        },
        line: {
          DEFAULT: '#2C2C2C', // was #1F1F1F
          2: '#3D3D3D', // gray-dark, extended strip (was #262626)
        },
        // Legacy alias — key kept so existing `ember-*` utilities resolve;
        // values now point at the Opal golds.
        ember: {
          DEFAULT: '#BB8B41',
          2: '#C2A670',
        },

        // Platform colors (not theme-driven)
        meta: '#0866FF',
        google: '#4285F4',
        tiktok: '#00F2EA',
        snapchat: '#FFFC00',
        whatsapp: '#25D366',

        // Status / data tokens
        'status-healthy': 'hsl(var(--status-healthy))',
        'status-critical': 'hsl(var(--status-critical))',
        success: 'hsl(var(--success))',
        warning: 'hsl(var(--warning))',
        danger: 'hsl(var(--danger))',
        info: 'hsl(var(--info))',
        insight: 'hsl(var(--insight))',
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '14px',
        xl: '16px',
        '2xl': '25px', // XML <card border-radius="25px"> (was 18px); sm–xl retained, no XML source
      },
      fontFamily: {
        // superads.xml typography — all three GROUNDED (extracted, not inferred)
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        // font-sans-secondary — Arabic/RTL surfaces
        'sans-arabic': ['Noto Sans Arabic', 'Segoe UI Arabic', 'Tahoma', 'sans-serif'],
      },
      fontSize: {
        micro: ['10px', { lineHeight: '1.4', fontWeight: '400' }],
        meta: ['11.5px', { lineHeight: '1.5', fontWeight: '500', letterSpacing: '0.06em' }],
        body: ['16px', { lineHeight: '1.5', fontWeight: '400' }], // XML body 16px/1.5em (was 14px — density change)
        'body-sm': ['14px', { lineHeight: '1.5', fontWeight: '400' }], // XML body small
        'body-lg': ['18px', { lineHeight: '1.5', fontWeight: '400' }], // XML body large
        // Dashboard-scale headings — retained sizes (no XML equivalent at this scale)
        h3: ['18px', { lineHeight: '1.35', fontWeight: '500', letterSpacing: '-0.01em' }],
        h2: ['22px', { lineHeight: '1.3', fontWeight: '500', letterSpacing: '-0.015em' }],
        h1: ['28px', { lineHeight: '1.2', fontWeight: '500', letterSpacing: '-0.02em' }],
        // Display scale — sizes align with XML desktop headings (h5/h4/h2);
        // weight 400 + 1.3 line-height per XML <headings weight="400" line-height="1.3em">
        'display-xs': ['32px', { lineHeight: '1.3', fontWeight: '400' }], // = XML h5 desktop
        'display-sm': ['40px', { lineHeight: '1.3', fontWeight: '400' }], // = XML h4 desktop
        'display-md': ['48px', { lineHeight: '1.3', fontWeight: '400' }], // = XML h3 desktop
        display: ['56px', { lineHeight: '1.3', fontWeight: '400' }], // = XML h2 desktop
        'display-lg': ['72px', { lineHeight: '1.1', fontWeight: '400' }], // retained, no XML source
      },
      boxShadow: {
        'glow-sm': '0 0 12px rgba(187, 139, 65, 0.18)',
        glow: '0 0 24px rgba(187, 139, 65, 0.22)',
        'glow-lg': '0 0 40px rgba(187, 139, 65, 0.28)',
        'glow-cyan': '0 0 24px rgba(57, 78, 108, 0.20)', // key kept for compat — now slate-blue
        'glow-orange': '0 0 24px rgba(194, 166, 112, 0.22)', // key kept for compat — now palette gold
        card: '0 1px 0 0 rgba(255, 255, 255, 0.04) inset, 0 1px 3px rgba(0, 0, 0, 0.25)',
        'card-hover': '0 1px 0 0 rgba(255, 255, 255, 0.06) inset, 0 8px 32px rgba(0, 0, 0, 0.4)',
        glass: '0 2px 8px rgba(0, 0, 0, 0.18)',
        elevated: '0 4px 24px rgba(0, 0, 0, 0.35)',
        bubble: '0 4px 12px rgba(0, 0, 0, 0.15)', // XML whatsapp-bubble shadow #00000026 0 4px 12px
      },
      spacing: {
        1: '4px',
        2: '8px',
        3: '12px',
        4: '16px', // = XML grid row-gap
        5: '24px', // = XML grid column-gap
        6: '32px',
        7: '48px',
        8: '64px',
        9: '96px',
        10: '128px',
        element: '27px', // XML <element-spacing>
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-primary': 'linear-gradient(135deg, #C2A670 0%, #BB8B41 50%, #C1A15A 100%)',
        'gradient-primary-soft':
          'linear-gradient(135deg, rgba(194, 166, 112, 0.10) 0%, rgba(187, 139, 65, 0.06) 100%)',
        'gradient-ember': 'linear-gradient(95deg, #BB8B41 0%, #C2A670 50%, #BB8B41 100%)',
        'gradient-void': 'linear-gradient(180deg, #000000 0%, #1A1A1A 100%)',
        // Legacy aliases — kept until Phase 4 sweep completes
        'gradient-cyber': 'linear-gradient(135deg, #C2A670 0%, #BB8B41 50%, #C1A15A 100%)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: 0 },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: 0 },
        },
        'slide-in-from-right': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'slide-in-from-left': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 },
        },
        'fade-up': {
          '0%': { opacity: 0, transform: 'translateY(12px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%': { opacity: 0, transform: 'scale(0.96)' },
          '100%': { opacity: 1, transform: 'scale(1)' },
        },
        'delta-pop': {
          '0%': { transform: 'scale(0.98)', opacity: 0.6 },
          '100%': { transform: 'scale(1)', opacity: 1 },
        },
        sweep: {
          '0%': { opacity: 0, transform: 'translateX(-12px)' },
          '100%': { opacity: 1, transform: 'translateX(0)' },
        },
        'glow-pulse': {
          '0%': { boxShadow: '0 0 0 rgba(0, 0, 0, 0)' },
          '60%': { boxShadow: '0 0 32px rgba(187, 139, 65, 0.25)' },
          '100%': { boxShadow: '0 0 0 rgba(0, 0, 0, 0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        orbit: {
          '0%': { transform: 'rotate(0deg) translateX(80px) rotate(0deg)' },
          '100%': { transform: 'rotate(360deg) translateX(80px) rotate(-360deg)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'slide-in': 'slide-in-from-right 0.3s ease-out',
        'slide-in-left': 'slide-in-from-left 0.3s ease-out',
        'fade-in': 'fade-in 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        enter: 'fade-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
        delta: 'delta-pop 0.2s cubic-bezier(0.16, 1, 0.3, 1) both',
        sweep: 'sweep 0.35s cubic-bezier(0.16, 1, 0.3, 1) both',
        'glow-pulse': 'glow-pulse 0.6s cubic-bezier(0.16, 1, 0.3, 1) both',
        'scale-in': 'scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        shimmer: 'shimmer 1.2s linear infinite',
        float: 'float 4s ease-in-out infinite',
        orbit: 'orbit 20s linear infinite',
      },
      transitionDuration: {
        fast: '120ms',
        base: '200ms', // matches XML button transition 0.2s
        slow: '350ms',
        xl: '500ms',
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.16, 1, 0.3, 1)',
        enter: 'cubic-bezier(0.16, 1, 0.3, 1)',
        exit: 'cubic-bezier(0.7, 0, 0.84, 0)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
