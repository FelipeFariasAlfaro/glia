import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppSelector } from '../../store';
import { selectIsAuthenticated, selectUserPermissions } from '../../store/authSlice';

/**
 * ProtectedRoute guards routes based on authentication and permissions.
 * It reads permissions from authSlice.permissions to determine access.
 * 
 * IMPORTANT: This component checks permissions from the Redux store.
 * OrderActions also performs independent permission checks. If the permission
 * model changes, BOTH components must be updated to stay consistent.
 * 
 * @see OrderActions.tsx - also checks permissions independently
 * @see authSlice.ts - source of truth for user permissions
 */
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: string;
  requiredRole?: string;
  fallbackPath?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredPermission,
  requiredRole,
  fallbackPath = '/login',
}) => {
  const location = useLocation();
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const permissions = useAppSelector(selectUserPermissions);
  const userRole = useAppSelector((state) => state.auth.user?.role);

  /** Check if user is authenticated at all */
  if (!isAuthenticated) {
    return <Navigate to={fallbackPath} state={{ from: location }} replace />;
  }

  /**
   * Permission check uses the permissions array from authSlice.
   * This is a flat string-based permission model (e.g., 'orders:cancel').
   * The same model is used in OrderActions for action-level gating.
   */
  if (requiredPermission && !permissions.includes(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  /** Role-based access check (admin, manager, agent) */
  if (requiredRole && userRole !== requiredRole) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};

/**
 * Higher-order component variant for class components or route configs.
 * Wraps a component with ProtectedRoute logic.
 */
export function withProtection<P extends object>(
  Component: React.ComponentType<P>,
  permission?: string
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute requiredPermission={permission}>
        <Component {...props} />
      </ProtectedRoute>
    );
  };
}
