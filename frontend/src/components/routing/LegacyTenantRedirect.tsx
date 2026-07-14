// components/routing/LegacyTenantRedirect.tsx
import { Navigate, useLocation, useParams } from 'react-router-dom';

export default function LegacyTenantRedirect() {
  const { tenantId } = useParams();
  const { pathname, search } = useLocation();
  const rest = pathname.replace(`/app/${tenantId}`, '') || '/overview';
  return <Navigate to={`/dashboard${rest}${search}`} replace />;
}
