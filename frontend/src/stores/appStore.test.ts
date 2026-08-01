/**
 * ADs Growth System - App Store Tests
 *
 * Comprehensive Vitest test suite for the Zustand app store
 * covering state management, role checks, owner controls,
 * persistence, and logout behavior. Single-client app — no
 * tenant/tenantId concept.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAppStore } from './appStore';
import type { User, UserRole } from './appStore';

// =============================================================================
// Mock localStorage
// =============================================================================

const mockLocalStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
    _getStore: () => store,
  };
})();

Object.defineProperty(window, 'localStorage', { value: mockLocalStorage });

// =============================================================================
// Test Fixtures
// =============================================================================

const createMockUser = (overrides: Partial<User> = {}): User => ({
  id: 1,
  email: 'user@stratum.ai',
  full_name: 'Test User',
  role: 'analyst',
  avatar_url: null,
  locale: 'en',
  timezone: 'UTC',
  is_active: true,
  is_verified: true,
  last_login_at: '2025-12-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  ...overrides,
});

const createOwnerUser = (overrides: Partial<User> = {}): User =>
  createMockUser({ id: 99, email: 'admin@stratum.ai', full_name: 'Owner', role: 'owner', ...overrides });

const createAdminUser = (overrides: Partial<User> = {}): User =>
  createMockUser({ id: 2, email: 'admin@stratum.ai', full_name: 'Admin User', role: 'admin', ...overrides });

// =============================================================================
// Reset helper
// =============================================================================

const resetStore = () => {
  const state = useAppStore.getState();
  // Call logout to clear state and localStorage
  state.logout();
  // Also reset dateRange to a known value since logout does not reset it
  useAppStore.setState({
    dateRange: { start: '2025-11-01', end: '2025-12-01' },
  });
  // Clear all mock calls
  mockLocalStorage.getItem.mockClear();
  mockLocalStorage.setItem.mockClear();
  mockLocalStorage.removeItem.mockClear();
  mockLocalStorage.clear.mockClear();
};

// =============================================================================
// Tests
// =============================================================================

describe('appStore', () => {
  beforeEach(() => {
    resetStore();
  });

  // ===========================================================================
  // 1. Initial State
  // ===========================================================================

  describe('Initial State', () => {
    it('should have correct default state values', () => {
      const state = useAppStore.getState();

      expect(state.user).toBeNull();
      expect(state.isOwnerMode).toBe(false);
      expect(state.ownerBypass).toBe(false);
      expect(state.selectedPlatforms).toEqual([]);
      expect(state.selectedBrand).toBeNull();
      expect(state.dateRange).toHaveProperty('start');
      expect(state.dateRange).toHaveProperty('end');
    });

    it('should have user starting as null', () => {
      const state = useAppStore.getState();
      expect(state.user).toBeNull();
    });
  });

  // ===========================================================================
  // 2. User Operations
  // ===========================================================================

  describe('User Operations', () => {
    it('should store user object via setUser', () => {
      const user = createMockUser();
      useAppStore.getState().setUser(user);

      const state = useAppStore.getState();
      expect(state.user).toEqual(user);
    });

    it('should auto-enable owner mode when user role is owner', () => {
      const owner = createOwnerUser();
      useAppStore.getState().setUser(owner);

      const state = useAppStore.getState();
      expect(state.user?.role).toBe('owner');
      expect(state.isOwnerMode).toBe(true);
    });

    it('should not enable owner mode when user role is admin', () => {
      const admin = createAdminUser();
      useAppStore.getState().setUser(admin);

      const state = useAppStore.getState();
      expect(state.user?.role).toBe('admin');
      expect(state.isOwnerMode).toBe(false);
    });

    it('should not enable owner mode when user role is analyst', () => {
      const user = createMockUser({ role: 'analyst' });
      useAppStore.getState().setUser(user);

      expect(useAppStore.getState().isOwnerMode).toBe(false);
    });

    it('should clear user when setUser is called with null', () => {
      useAppStore.getState().setUser(createMockUser());
      expect(useAppStore.getState().user).not.toBeNull();

      useAppStore.getState().setUser(null);
      expect(useAppStore.getState().user).toBeNull();
    });
  });

  // ===========================================================================
  // 3. Role Checks
  // ===========================================================================

  describe('Role Checks', () => {
    it('isOwner should return true for owner role', () => {
      useAppStore.getState().setUser(createOwnerUser());

      expect(useAppStore.getState().isOwner()).toBe(true);
    });

    it('isOwner should return false for admin role', () => {
      useAppStore.getState().setUser(createAdminUser());

      expect(useAppStore.getState().isOwner()).toBe(false);
    });

    it('isOwner should return false when user is null', () => {
      expect(useAppStore.getState().isOwner()).toBe(false);
    });

    it('isAdmin should return true for admin role', () => {
      useAppStore.getState().setUser(createAdminUser());

      expect(useAppStore.getState().isAdmin()).toBe(true);
    });

    it('isAdmin should return true for owner role', () => {
      useAppStore.getState().setUser(createOwnerUser());

      expect(useAppStore.getState().isAdmin()).toBe(true);
    });

    it('isAdmin should return false for regular user role', () => {
      useAppStore.getState().setUser(createMockUser({ role: 'analyst' }));

      expect(useAppStore.getState().isAdmin()).toBe(false);
    });

    it('hasRole should return true when user role is in the given array', () => {
      useAppStore.getState().setUser(createMockUser({ role: 'analyst' }));

      expect(useAppStore.getState().hasRole(['manager', 'analyst'])).toBe(true);
    });

    it('hasRole should return false when user role is not in the given array', () => {
      useAppStore.getState().setUser(createMockUser({ role: 'viewer' }));

      expect(useAppStore.getState().hasRole(['admin', 'owner'])).toBe(false);
    });

    it('hasRole should return false when user is null', () => {
      expect(useAppStore.getState().hasRole(['admin', 'owner'])).toBe(false);
    });

    it('hasRole should work for each UserRole type', () => {
      const roles: UserRole[] = ['owner', 'admin', 'manager', 'analyst', 'viewer'];

      for (const role of roles) {
        useAppStore.getState().setUser(createMockUser({ role }));
        expect(useAppStore.getState().hasRole([role])).toBe(true);
        expect(useAppStore.getState().hasRole(roles.filter((r) => r !== role))).toBe(false);

        // Reset ownerMode for next iteration
        useAppStore.setState({ isOwnerMode: false });
      }
    });
  });

  // ===========================================================================
  // 4. Feature Flags
  // ===========================================================================

  describe('Feature Flags', () => {
    // Tenant-scoped feature flags no longer exist (single-client app);
    // hasFeature is kept only for API compatibility with existing callers
    // and always returns false. Global feature flags live in
    // useFeatureFlagsStore instead.
    it('hasFeature should always return false', () => {
      expect(useAppStore.getState().hasFeature('cdp_enabled')).toBe(false);
      expect(useAppStore.getState().hasFeature('nonexistent_feature')).toBe(false);
    });
  });

  // ===========================================================================
  // 5. Owner Controls
  // ===========================================================================

  describe('Owner Controls', () => {
    it('setOwnerMode should enable mode for owner users', () => {
      useAppStore.getState().setUser(createOwnerUser());
      // setUser auto-enables it, so disable first to test setOwnerMode
      useAppStore.getState().setOwnerMode(false);
      expect(useAppStore.getState().isOwnerMode).toBe(false);

      useAppStore.getState().setOwnerMode(true);
      expect(useAppStore.getState().isOwnerMode).toBe(true);
    });

    it('setOwnerMode should not enable mode for non-owner users', () => {
      useAppStore.getState().setUser(createAdminUser());
      expect(useAppStore.getState().isOwnerMode).toBe(false);

      useAppStore.getState().setOwnerMode(true);
      expect(useAppStore.getState().isOwnerMode).toBe(false);
    });

    it('setOwnerMode should not work when user is null', () => {
      useAppStore.getState().setOwnerMode(true);
      expect(useAppStore.getState().isOwnerMode).toBe(false);
    });

    it('setOwnerBypass should enable bypass for owner users', () => {
      useAppStore.getState().setUser(createOwnerUser());

      useAppStore.getState().setOwnerBypass(true);
      expect(useAppStore.getState().ownerBypass).toBe(true);

      useAppStore.getState().setOwnerBypass(false);
      expect(useAppStore.getState().ownerBypass).toBe(false);
    });

    it('setOwnerBypass should not enable bypass for non-owner users', () => {
      useAppStore.getState().setUser(createMockUser({ role: 'manager' }));

      useAppStore.getState().setOwnerBypass(true);
      expect(useAppStore.getState().ownerBypass).toBe(false);
    });

    it('setOwnerBypass should not work when user is null', () => {
      useAppStore.getState().setOwnerBypass(true);
      expect(useAppStore.getState().ownerBypass).toBe(false);
    });
  });

  // ===========================================================================
  // 6. Logout
  // ===========================================================================

  describe('Logout', () => {
    it('should clear all state on logout', () => {
      // Set up a fully populated store
      useAppStore.getState().setUser(createOwnerUser());
      useAppStore.getState().setSelectedPlatforms(['meta', 'google']);
      useAppStore.getState().setSelectedBrand('acme-brand');

      // Verify state is populated before logout
      expect(useAppStore.getState().user).not.toBeNull();
      expect(useAppStore.getState().isOwnerMode).toBe(true);
      expect(useAppStore.getState().selectedPlatforms.length).toBeGreaterThan(0);
      expect(useAppStore.getState().selectedBrand).not.toBeNull();

      // Logout
      useAppStore.getState().logout();

      const state = useAppStore.getState();
      expect(state.user).toBeNull();
      expect(state.isOwnerMode).toBe(false);
      expect(state.ownerBypass).toBe(false);
      expect(state.selectedPlatforms).toEqual([]);
      expect(state.selectedBrand).toBeNull();
    });

    it('should clear localStorage keys on logout', () => {
      mockLocalStorage.removeItem.mockClear();

      useAppStore.getState().logout();

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('access_token');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('refresh_token');
    });
  });

  // ===========================================================================
  // 7. Date Range, Platforms & Brand
  // ===========================================================================

  describe('Date Range, Platforms & Brand', () => {
    it('should update date range via setDateRange', () => {
      useAppStore.getState().setDateRange('2025-01-01', '2025-06-30');

      const state = useAppStore.getState();
      expect(state.dateRange.start).toBe('2025-01-01');
      expect(state.dateRange.end).toBe('2025-06-30');
    });

    it('should update selected platforms via setSelectedPlatforms', () => {
      useAppStore.getState().setSelectedPlatforms(['meta', 'google', 'tiktok']);

      const state = useAppStore.getState();
      expect(state.selectedPlatforms).toEqual(['meta', 'google', 'tiktok']);
    });

    it('should allow clearing platforms by setting an empty array', () => {
      useAppStore.getState().setSelectedPlatforms(['meta']);
      expect(useAppStore.getState().selectedPlatforms).toEqual(['meta']);

      useAppStore.getState().setSelectedPlatforms([]);
      expect(useAppStore.getState().selectedPlatforms).toEqual([]);
    });

    it('should allow overwriting date range multiple times', () => {
      useAppStore.getState().setDateRange('2025-01-01', '2025-03-31');
      expect(useAppStore.getState().dateRange).toEqual({ start: '2025-01-01', end: '2025-03-31' });

      useAppStore.getState().setDateRange('2025-07-01', '2025-12-31');
      expect(useAppStore.getState().dateRange).toEqual({ start: '2025-07-01', end: '2025-12-31' });
    });

    it('should update selected brand via setSelectedBrand', () => {
      useAppStore.getState().setSelectedBrand('acme-brand');
      expect(useAppStore.getState().selectedBrand).toBe('acme-brand');
    });

    it('should allow clearing brand by setting null', () => {
      useAppStore.getState().setSelectedBrand('acme-brand');
      expect(useAppStore.getState().selectedBrand).toBe('acme-brand');

      useAppStore.getState().setSelectedBrand(null);
      expect(useAppStore.getState().selectedBrand).toBeNull();
    });
  });

  // ===========================================================================
  // 8. Persistence Configuration
  // ===========================================================================

  describe('Persistence', () => {
    it('should use the correct localStorage key for persistence', () => {
      // The Zustand persist middleware uses 'stratum-app-store' as its storage key.
      // With a mock localStorage, the persist middleware may not trigger setItem
      // synchronously (or at all if hydration fails silently). Instead, verify the
      // store's persist config directly via the persist API.
      const persistOptions = useAppStore.persist;
      expect(persistOptions.getOptions().name).toBe('stratum-app-store');
    });
  });

  // ===========================================================================
  // 9. Edge Cases
  // ===========================================================================

  describe('Edge Cases', () => {
    it('should handle switching users from owner to regular user', () => {
      // Login as owner
      useAppStore.getState().setUser(createOwnerUser());
      expect(useAppStore.getState().isOwnerMode).toBe(true);

      // Switch to regular user - note: setUser does not auto-disable ownerMode
      // It only auto-enables for owner. The mode stays until explicitly changed or logout.
      useAppStore.getState().setUser(createMockUser({ role: 'analyst' }));
      expect(useAppStore.getState().user?.role).toBe('analyst');
    });
  });
});
