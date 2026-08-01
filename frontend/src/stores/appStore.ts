/**
 * ADs Growth System - App Store
 *
 * Zustand store for managing session/user state and dashboard UI
 * preferences. Single-client app — no tenant context, no tenant ID.
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

export interface AppState {
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

  // Brand filter (spec §5.4) — the active Brand/client scope for
  // MANAGER/ANALYST views; null means "all brands".
  selectedBrand: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setOwnerMode: (enabled: boolean) => void;
  setOwnerBypass: (enabled: boolean) => void;
  setDateRange: (start: string, end: string) => void;
  setSelectedPlatforms: (platforms: string[]) => void;
  setSelectedBrand: (brand: string | null) => void;
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

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        user: null,
        isOwnerMode: false,
        ownerBypass: false,
        dateRange: initialDateRange(),
        selectedPlatforms: [],
        selectedBrand: null,

        // Actions
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

        setSelectedBrand: (brand) => {
          set({ selectedBrand: brand });
        },

        logout: () => {
          set({
            user: null,
            isOwnerMode: false,
            ownerBypass: false,
            selectedPlatforms: [],
            selectedBrand: null,
          });
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

        // Feature flags are no longer tenant-scoped (single-client app);
        // global feature flags live in useFeatureFlagsStore. Kept as a
        // no-op for API compatibility with existing callers.
        hasFeature: () => {
          return false;
        },
      }),
      {
        name: 'stratum-app-store',
        storage: createJSONStorage(() => localStorage),
        // Only persist non-sensitive UI preferences — never persist privilege
        // escalation flags like ownerBypass (must be re-asserted each session).
        partialize: (state) => ({
          dateRange: state.dateRange,
          selectedPlatforms: state.selectedPlatforms,
          selectedBrand: state.selectedBrand,
          isOwnerMode: state.isOwnerMode,
        }),
      }
    ),
    { name: 'AppStore' }
  )
);

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

export const selectUser = (state: AppState) => state.user;
export const selectIsOwnerMode = (state: AppState) => state.isOwnerMode;
export const selectDateRange = (state: AppState) => state.dateRange;
export const selectSelectedPlatforms = (state: AppState) => state.selectedPlatforms;
export const selectSelectedBrand = (state: AppState) => state.selectedBrand;

// =============================================================================
// Hooks for specific state slices
// =============================================================================

export const useUser = () => useAppStore(selectUser);
export const useIsOwnerMode = () => useAppStore(selectIsOwnerMode);
export const useDateRange = () => useAppStore(selectDateRange);
export const useSelectedPlatforms = () => useAppStore(selectSelectedPlatforms);
export const useSelectedBrand = () => useAppStore(selectSelectedBrand);

// =============================================================================
// Action hooks
// =============================================================================

export const useAppActions = () => {
  const setUser = useAppStore((state) => state.setUser);
  const setOwnerMode = useAppStore((state) => state.setOwnerMode);
  const setOwnerBypass = useAppStore((state) => state.setOwnerBypass);
  const setDateRange = useAppStore((state) => state.setDateRange);
  const setSelectedPlatforms = useAppStore((state) => state.setSelectedPlatforms);
  const setSelectedBrand = useAppStore((state) => state.setSelectedBrand);
  const logout = useAppStore((state) => state.logout);

  return {
    setUser,
    setOwnerMode,
    setOwnerBypass,
    setDateRange,
    setSelectedPlatforms,
    setSelectedBrand,
    logout,
  };
};
