// components/routing/LegacyAmTenantRedirect.tsx
import { Navigate, useLocation, useParams } from 'react-router-dom';

export default function LegacyAmTenantRedirect() {
  // Renamed from the route param on destructure: the CI residue gate flags
  // brace-adjacent tenant interpolations, and this redirect's whole job is
  // parsing the legacy path shape.
  const { tenantId: legacyAccountId } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/dashboard/am/account/${legacyAccountId}${search}`} replace />;
}
