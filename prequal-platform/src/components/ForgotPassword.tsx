import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/client';
import './Auth.css';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await authApi.requestPasswordReset(email);
      setIsSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Check Your Email</h1>
          <p className="auth-subtitle">
            If an account exists with that email, we've sent password reset instructions.
          </p>
          <p className="auth-footer">
            Remember your password? <Link to="/login">Sign In</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Reset Password</h1>
        <p className="auth-subtitle">Enter your email to receive reset instructions</p>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="form-input"
              placeholder="Enter your email"
            />
          </div>

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Sending...' : 'Send Reset Link'}
          </button>
        </form>

        <p className="auth-footer">
          Remember your password? <Link to="/login">Sign In</Link>
        </p>
      </div>
    </div>
  );
};

export default ForgotPassword;