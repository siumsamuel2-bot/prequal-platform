import { useState, FormEvent, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { authApi } from '../api/client';
import './Auth.css';

const ResetPassword = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link. Please request a new password reset.');
    }
  }, [token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('Invalid reset link');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      await authApi.confirmPasswordReset(token, password);
      navigate('/login', { state: { message: 'Password reset successful. Please log in.' } });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password reset failed');
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Invalid Reset Link</h1>
          <p className="auth-subtitle">This password reset link is invalid or has expired.</p>
          <p className="auth-footer">
            <Link to="/forgot-password">Request a new reset</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Set New Password</h1>
        <p className="auth-subtitle">Enter your new password below</p>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="password">New Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="form-input"
              placeholder="Enter new password"
              minLength={8}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="form-input"
              placeholder="Confirm new password"
            />
          </div>

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Resetting...' : 'Reset Password'}
          </button>
        </form>

        <p className="auth-footer">
          Remember your password? <Link to="/login">Sign In</Link>
        </p>
      </div>
    </div>
  );
};

export default ResetPassword;