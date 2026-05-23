import React, { Component, ErrorInfo } from 'react';
import { reportError } from '../../utils/errorReporting';

/**
 * ErrorBoundary catches JavaScript errors in child component tree during rendering.
 * Provides retry functionality and reports errors to Sentry.
 * 
 * LIMITATION: React Error Boundaries only catch errors during rendering,
 * lifecycle methods, and constructors. They do NOT catch:
 * - Errors in event handlers
 * - Asynchronous errors (setTimeout, requestAnimationFrame)
 * - Errors in async hooks (useEffect async callbacks)
 * 
 * This means errors from useWebSocket (which are async/event-driven)
 * will NOT be caught by this boundary. WebSocket disconnection errors
 * and async data fetching errors bypass ErrorBoundary entirely.
 * 
 * @see useWebSocket.ts - errors from this hook bypass ErrorBoundary
 * @see errorReporting.ts - Sentry integration for error tracking
 */
interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private maxRetries = 3;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    /** Report to Sentry with component stack context */
    reportError(error, {
      componentStack: errorInfo.componentStack || '',
      retryCount: this.state.retryCount,
      boundary: 'ErrorBoundary',
    });
    this.props.onError?.(error, errorInfo);
  }

  /** Retry rendering the children — resets error state */
  handleRetry = (): void => {
    if (this.state.retryCount < this.maxRetries) {
      this.setState((prev) => ({
        hasError: false,
        error: null,
        retryCount: prev.retryCount + 1,
      }));
    }
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="error-boundary-fallback" role="alert">
          <h3>Something went wrong</h3>
          <p className="error-message">{this.state.error?.message}</p>
          {this.state.retryCount < this.maxRetries && (
            <button onClick={this.handleRetry} className="retry-button">
              Retry ({this.maxRetries - this.state.retryCount} attempts remaining)
            </button>
          )}
          {this.state.retryCount >= this.maxRetries && (
            <p className="max-retries">Maximum retries reached. Please refresh the page.</p>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
