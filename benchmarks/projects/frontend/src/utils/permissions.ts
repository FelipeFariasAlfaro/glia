/**
 * Permission checking utilities for role-based access control.
 * 
 * The permission model uses flat string-based permissions in the format:
 * 'resource:action' (e.g., 'orders:cancel', 'analytics:view').
 * 
 * IMPORTANT: Both ProtectedRoute and OrderActions use these utilities
 * (or equivalent inline checks) to verify permissions. They read from
 * the same source (authSlice.user.permissions) but check independently.
 * If the permission format changes (e.g., to hierarchical like
 * 'orders.write.cancel'), ALL consumers must be updated.
 * 
 * @see ProtectedRoute.tsx - route-level permission checks
 * @see OrderActions.tsx - action-level permission checks
 * @see authSlice.ts - permission data source
 */

/** Standard permission format: 'resource:action' */
export type Permission = string;

/** Role definitions with their default permissions */
export const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  admin: [
    'orders:view', 'orders:cancel', 'orders:refund', 'orders:resend',
    'analytics:view', 'users:manage', 'settings:edit',
  ],
  manager: [
    'orders:view', 'orders:cancel', 'orders:refund',
    'analytics:view',
  ],
  agent: [
    'orders:view', 'orders:cancel',
  ],
  viewer: [
    'orders:view',
  ],
};

/**
 * Check if a user has a specific permission.
 * Uses exact string matching against the permissions array.
 */
export function hasPermission(userPermissions: Permission[], required: Permission): boolean {
  return userPermissions.includes(required);
}

/**
 * Check if a user has ALL of the specified permissions.
 * Used for actions that require multiple permissions.
 */
export function hasAllPermissions(userPermissions: Permission[], required: Permission[]): boolean {
  return required.every((perm) => userPermissions.includes(perm));
}

/**
 * Check if a user has ANY of the specified permissions.
 * Used for showing UI elements that have multiple access paths.
 */
export function hasAnyPermission(userPermissions: Permission[], required: Permission[]): boolean {
  return required.some((perm) => userPermissions.includes(perm));
}

/**
 * Get the default permissions for a role.
 * Falls back to empty array for unknown roles.
 */
export function getPermissionsForRole(role: string): Permission[] {
  return ROLE_PERMISSIONS[role] || [];
}

/**
 * Check if a permission string matches the expected format.
 * Valid format: 'resource:action' where both parts are non-empty.
 */
export function isValidPermission(permission: string): boolean {
  const parts = permission.split(':');
  return parts.length === 2 && parts[0].length > 0 && parts[1].length > 0;
}

/**
 * Extract the resource part from a permission string.
 * e.g., 'orders:cancel' → 'orders'
 */
export function getResource(permission: Permission): string {
  return permission.split(':')[0];
}

/**
 * Extract the action part from a permission string.
 * e.g., 'orders:cancel' → 'cancel'
 */
export function getAction(permission: Permission): string {
  return permission.split(':')[1];
}
