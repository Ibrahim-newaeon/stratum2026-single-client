/**
 * Stratum AI - Tenant Store
 *
 * Zustand store for managing tenant context and user session state.
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { devtools } from 'zustand/middleware';

// =============================================================================
// Types
// =============================================================================

/**
 * The 5 backend roles (matches UserRole enum in base_models.py).
 * Semantic aliases: manager=account_mgr, analyst=media_buyer, viewer=client_viewer
 */
export type UserRole =
  | 'owner'
  | 'admin'
  | 'manager'
  | 'analyst'
  | 'viewer';

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: UserRole;
  avatar_url: string | null;
  locale: string;
  timezone: string;
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  domain: string | null;
  plan: string;
  plan_expires_at: string | null;
  max_users: number;
  max_campaigns: number;
  settings: Record<string, any>;
  feature_flags: Record<string, boolean>;
  created_at: string;
  updated_at: string;
}

export interface TenantState {
  // Current tenant context
  tenantId: number | null;
  tenant: Tenant | null;

  // Current user
  user: User | null;

  // UI state
  isOwnerMode: boolean;
  ownerBypass: boolean;

  // Date range for analytics
  dateRange: {
    start: string;
    end: string;
  };

  // Platform filter
  selectedPlatforms: string[];

  // Actions
  setTenantId: (tenantId: number | null) => void;
  setTenant: (tenant: Tenant | null) => void;
  setUser: (user: User | null) => void;
  setOwnerMode: (enabled: boolean) => void;
  setOwnerBypass: (enabled: boolean) => void;
  setDateRange: (start: string, end: string) => void;
  setSelectedPlatforms: (platforms: string[]) => void;
  logout: () => void;

  // Computed
  isOwner: () => boolean;
  isAdmin: () => boolean;
  hasRole: (roles: UserRole[]) => boolean;
  hasFeature: (feature: string) => boolean;
}

// =============================================================================
// Store
// =============================================================================

const initialDateRange = () => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);

  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
};

export const useTenantStore = create<TenantState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        tenantId: null,
        tenant: null,
        user: null,
        isOwnerMode: false,
        ownerBypass: false,
        dateRange: initialDateRange(),
        selectedPlatforms: [],

        // Actions
        setTenantId: (tenantId) => {
          set({ tenantId });
          // Also update localStorage for API client
          if (tenantId) {
            localStorage.setItem('tenant_id', String(tenantId));
          } else {
            localStorage.removeItem('tenant_id');
          }
        },

        setTenant: (tenant) => {
          set({ tenant, tenantId: tenant?.id ?? null });
          if (tenant) {
            localStorage.setItem('tenant_id', String(tenant.id));
          }
        },

        setUser: (user) => {
          set({ user });
          // Auto-enable owner mode if user is owner
          if (user?.role === 'owner') {
            set({ isOwnerMode: true });
          }
        },

        setOwnerMode: (enabled) => {
          const state = get();
          // Only allow if user is actually an owner
          if (state.user?.role === 'owner') {
            set({ isOwnerMode: enabled });
          }
        },

        setOwnerBypass: (enabled) => {
          const state = get();
          // Only allow if user is owner
          if (state.user?.role === 'owner') {
            set({ ownerBypass: enabled });
          }
        },

        setDateRange: (start, end) => {
          set({ dateRange: { start, end } });
        },

        setSelectedPlatforms: (platforms) => {
          set({ selectedPlatforms: platforms });
        },

        logout: () => {
          set({
            tenantId: null,
            tenant: null,
            user: null,
            isOwnerMode: false,
            ownerBypass: false,
            selectedPlatforms: [],
          });
          localStorage.removeItem('tenant_id');
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        },

        // Computed
        isOwner: () => {
          const state = get();
          return state.user?.role === 'owner';
        },

        isAdmin: () => {
          const state = get();
          return state.user?.role === 'owner' || state.user?.role === 'admin';
        },

        hasRole: (roles) => {
          const state = get();
          if (!state.user) return false;
          return roles.includes(state.user.role);
        },

        hasFeature: (feature) => {
          const state = get();
          if (!state.tenant?.feature_flags) return false;
          return state.tenant.feature_flags[feature] === true;
        },
      }),
      {
        name: 'stratum-tenant-store',
        storage: createJSONStorage(() => localStorage),
        // Only persist non-sensitive UI preferences — never persist privilege
        // escalation flags like ownerBypass (must be re-asserted each session).
        partialize: (state) => ({
          tenantId: state.tenantId,
          dateRange: state.dateRange,
          selectedPlatforms: state.selectedPlatforms,
          isOwnerMode: state.isOwnerMode,
        }),
      }
    ),
    { name: 'TenantStore' }
  )
);

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

export const selectTenantId = (state: TenantState) => state.tenantId;
export const selectTenant = (state: TenantState) => state.tenant;
export const selectUser = (state: TenantState) => state.user;
export const selectIsOwnerMode = (state: TenantState) => state.isOwnerMode;
export const selectDateRange = (state: TenantState) => state.dateRange;
export const selectSelectedPlatforms = (state: TenantState) => state.selectedPlatforms;

// =============================================================================
// Hooks for specific state slices
// =============================================================================

export const useTenantId = () => useTenantStore(selectTenantId);
export const useTenant = () => useTenantStore(selectTenant);
export const useUser = () => useTenantStore(selectUser);
export const useIsOwnerMode = () => useTenantStore(selectIsOwnerMode);
export const useDateRange = () => useTenantStore(selectDateRange);
export const useSelectedPlatforms = () => useTenantStore(selectSelectedPlatforms);

// =============================================================================
// Action hooks
// =============================================================================

export const useTenantActions = () => {
  const setTenantId = useTenantStore((state) => state.setTenantId);
  const setTenant = useTenantStore((state) => state.setTenant);
  const setUser = useTenantStore((state) => state.setUser);
  const setOwnerMode = useTenantStore((state) => state.setOwnerMode);
  const setOwnerBypass = useTenantStore((state) => state.setOwnerBypass);
  const setDateRange = useTenantStore((state) => state.setDateRange);
  const setSelectedPlatforms = useTenantStore((state) => state.setSelectedPlatforms);
  const logout = useTenantStore((state) => state.logout);

  return {
    setTenantId,
    setTenant,
    setUser,
    setOwnerMode,
    setOwnerBypass,
    setDateRange,
    setSelectedPlatforms,
    logout,
  };
};
