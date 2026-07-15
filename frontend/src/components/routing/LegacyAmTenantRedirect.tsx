// components/routing/LegacyAmTenantRedirect.tsx
import { Navigate, useLocation, useParams } from 'react-router-dom';

export default function LegacyAmTenantRedirect() {
  const { tenantId } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/dashboard/am/account/${tenantId}${search}`} replace />;
}
