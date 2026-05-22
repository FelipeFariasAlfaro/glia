/**
 * Error reporting utility using Sentry for production error tracking.
 * Provides context-enriched error reports with user and session info.
 * 
 * SCOPE OF CAPTURE:
 * - ErrorBoundary catches render errors and reports them here
 * - Axios client reports 5xx API errors here
 * - Manual calls from components for handled errors
 * 
 * LIMITATION: Async errors from hooks (like useWebSocket) that are not
 * caught by ErrorBoundary are only reported if the hook explicitly calls
 * reportError. Currently, useWebSocket does NOT call reportError on
 * connection errors — those errors are logged to console only.
 * 
 * @see ErrorBoundary.tsx - reports caught render errors
 * @see client.ts - reports 5xx API errors
 * @see useWebSocket.ts - does NOT report errors here (console only)
 */

interface ErrorContext {
  [key: string]: any;
}

interface UserContext {
  id: string;
  email: string;
  role: string;
}

/** Sentry-like error reporting interface */
let sentryInitialized = false;
let currentUser: UserContext | null = null;

/**
 * Initialize error reporting with DSN and environment config.
 * Should be called once at app startup.
 */
export function initErrorReporting(config: {
  dsn: string;
  environment: string;
  release?: string;
}): void {
  // In production, this would call Sentry.init()
  sentryInitialized = true;
  console.info('[ErrorReporting] Initialized', { environment: config.environment });
}

/**
 * Set the current user context for error reports.
 * Called after successful login to attach user info to errors.
 */
export function setUserContext(user: UserContext): void {
  currentUser = user;
  // Sentry.setUser(user)
}

/** Clear user context on logout */
export function clearUserContext(): void {
  currentUser = null;
  // Sentry.setUser(null)
}

/**
 * Report an error with additional context.
 * Enriches the error with user info, timestamp, and custom context.
 * 
 * Used by ErrorBoundary for render errors and Axios client for API errors.
 * NOT used by useWebSocket — those errors go to console only.
 */
export function reportError(error: Error, context?: ErrorContext): void {
  if (!sentryInitialized) {
    console.error('[ErrorReporting] Not initialized, error:', error, context);
    return;
  }

  const enrichedContext = {
    ...context,
    timestamp: new Date().toISOString(),
    user: currentUser ? { id: currentUser.id, role: currentUser.role } : undefined,
    url: typeof window !== 'undefined' ? window.location.href : undefined,
  };

  // In production: Sentry.captureException(error, { extra: enrichedContext })
  console.error('[ErrorReporting] Captured:', error.message, enrichedContext);
}

/**
 * Report a warning-level event (non-fatal issues).
 * Used for degraded functionality like WebSocket disconnects.
 */
export function reportWarning(message: string, context?: ErrorContext): void {
  if (!sentryInitialized) return;
  // Sentry.captureMessage(message, { level: 'warning', extra: context })
  console.warn('[ErrorReporting] Warning:', message, context);
}

/**
 * Create a breadcrumb for debugging context.
 * Breadcrumbs help trace the sequence of events leading to an error.
 */
export function addBreadcrumb(category: string, message: string, data?: Record<string, any>): void {
  // Sentry.addBreadcrumb({ category, message, data, timestamp: Date.now() / 1000 })
}
