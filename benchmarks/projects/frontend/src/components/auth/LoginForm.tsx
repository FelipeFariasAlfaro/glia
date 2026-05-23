import React, { useState, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useAppDispatch } from '../../store';
import { setCredentials, setLoginError } from '../../store/authSlice';

/**
 * LoginForm component handles user authentication with email/password.
 * Includes client-side validation and "Remember Me" functionality.
 * The "Remember Me" checkbox controls whether tokens are stored in
 * localStorage (persistent) or sessionStorage (session-only).
 * @see tokenStorage.ts for storage strategy details
 */
interface LoginFormProps {
  onSuccess?: () => void;
  redirectPath?: string;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, redirectPath = '/dashboard' }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const { login, isLoading, error } = useAuth();
  const dispatch = useAppDispatch();

  /** Validates form fields before submission */
  const validate = useCallback((): boolean => {
    const errors: Record<string, string> = {};
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Valid email is required';
    }
    if (!password || password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [email, password]);

  /**
   * Handles form submission. On success, stores tokens based on rememberMe flag.
   * The rememberMe preference is passed to the auth API and also determines
   * the storage mechanism used by tokenStorage utility.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      const result = await login({ email, password, rememberMe });
      dispatch(setCredentials({
        user: result.user,
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        rememberMe,
      }));
      onSuccess?.();
    } catch (err: any) {
      dispatch(setLoginError(err.message || 'Login failed'));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="login-form" aria-label="Login form">
      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={!!validationErrors.email} />
        {validationErrors.email && <span className="error" role="alert">{validationErrors.email}</span>}
      </div>
      <div className="form-field">
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={!!validationErrors.password} />
        {validationErrors.password && <span className="error" role="alert">{validationErrors.password}</span>}
      </div>
      <div className="form-field">
        <label><input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} /> Remember me</label>
      </div>
      <button type="submit" disabled={isLoading}>{isLoading ? 'Signing in...' : 'Sign In'}</button>
      {error && <div className="login-error" role="alert">{error}</div>}
    </form>
  );
};
