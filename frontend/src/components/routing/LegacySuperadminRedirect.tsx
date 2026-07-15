// components/routing/LegacySuperadminRedirect.tsx
import { Navigate, useLocation } from 'react-router-dom';

// The old superadmin shell lived at /dashboard/superadmin/*. Its
// replacement is the platform console at /console/* — map the trailing
// segment through so bookmarks like /dashboard/superadmin/users land on
// /console/users (spec §5.1 legacy redirects).
export default function LegacySuperadminRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace('/dashboard/superadmin', '');
  return <Navigate to={`/console${rest}${search}`} replace />;
}
