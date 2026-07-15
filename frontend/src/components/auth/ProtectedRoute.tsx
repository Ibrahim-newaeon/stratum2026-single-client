/**
 * Protected Route Component
 * Wraps routes that require authentication.
 *
 * Role hierarchy (mirrors backend ROLE_HIERARCHY in auth/permissions.py):
 *   OWNER:      100  — Platform owner, console access
 *   ADMIN:       80  — Full organization access, user management
 *   MANAGER:     60  — Campaign management
 *   ANALYST:     40  — Campaign execution, analytics
 *   VIEWER:      10  — Portal scope (read-only)
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/common/LoadingSpinner';

/** All five backend roles */
export type AppRole = 'owner' | 'admin' | 'manager' | 'analyst' | 'viewer';

/** Numeric hierarchy matching backend ROLE_HIERARCHY exactly */
const ROLE_HIERARCHY: Record<AppRole, number> = {
  owner: 100,
  admin: 80,
  manager: 60,
  analyst: 40,
  viewer: 10,
};

/** Check if a user role meets the minimum required role */
export function meetsRoleRequirement(userRole: string, requiredRole: AppRole): boolean {
  const userLevel = ROLE_HIERARCHY[userRole as AppRole] ?? 0;
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
  return userLevel >= requiredLevel;
}

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: AppRole;
  requiredPermission?: string;
  /** If true, only portal (VIEWER) users can access this route */
  portalOnly?: boolean;
  /** If true, only agency users (non-portal) can access this route */
  agencyOnly?: boolean;
}

export default function ProtectedRoute({
  children,
  requiredRole,
  requiredPermission,
  portalOnly,
  agencyOnly,
}: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // Show loading while checking auth state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Portal / agency user type gating
  if (portalOnly && user && user.user_type !== 'portal') {
    return <Navigate to="/unauthorized" replace />;
  }
  if (agencyOnly && user && user.user_type === 'portal') {
    return <Navigate to="/portal" replace />;
  }

  // Check role hierarchy (all 5 roles supported)
  if (requiredRole && user) {
    if (!meetsRoleRequirement(user.role, requiredRole)) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  // Check specific permission
  if (requiredPermission && user) {
    const hasPermission =
      user.permissions.includes('all') || user.permissions.includes(requiredPermission);
    if (!hasPermission) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <>{children}</>;
}
