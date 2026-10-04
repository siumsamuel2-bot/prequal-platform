import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authApi } from '../api/client';
import { login as authLogin } from '../utils/auth';
import './Auth.css';

const Login = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaUserId, setMfaUserId] = useState('');
  const [mfaToken, setMfaToken] = useState('');

  const handleLoginSuccess = (accessToken: string) => {
    authLogin(accessToken);

    authApi.getMe().then(user => {
      authLogin(accessToken, user);
    }).catch(() => {});

    navigate('/dashboard');
  };

  const handleLoginSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await authApi.login(username, password);
      handleLoginSuccess(response.access_token);
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('MFA_REQUIRED:')) {
        const userId = err.message.split(':')[1];
        setMfaUserId(userId);
        setMfaRequired(true);
        setError('');
      } else {
        setError(err instanceof Error ? err.message : 'Invalid credentials');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleMfaSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await authApi.validateMFA(mfaUserId, mfaToken);
      handleLoginSuccess(response.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid MFA code');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBackToLogin = () => {
    setMfaRequired(false);
    setMfaUserId('');
    setMfaToken('');
    setError('');
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Prequal</h1>
        <p className="auth-subtitle">Subcontractor Compliance Platform</p>

        {mfaRequired ? (
          <form onSubmit={handleMfaSubmit} className="auth-form">
            <div className="auth-mfa-icon">🔐</div>
            <p className="auth-mfa-title">Two-Factor Authentication</p>
            <p className="auth-mfa-desc">
              Enter the 6-digit code from your authenticator app, or one of your backup codes
            </p>

            {error && <div className="auth-error">{error}</div>}

            <div className="form-group">
              <label htmlFor="mfaToken">Verification Code</label>
              <input
                type="text"
                id="mfaToken"
                value={mfaToken}
                onChange={(e) => setMfaToken(e.target.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase().slice(0, 12))}
                required
                className="form-input"
                placeholder="000000"
                maxLength={12}
                autoFocus
              />
            </div>

            <button type="submit" className="auth-button" disabled={isLoading}>
              {isLoading ? 'Verifying...' : 'Verify'}
            </button>

            <button type="button" onClick={handleBackToLogin} className="auth-button-secondary">
              Back to Login
            </button>
          </form>
        ) : (
          <form onSubmit={handleLoginSubmit} className="auth-form">
            {error && <div className="auth-error">{error}</div>}

            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="form-input"
                placeholder="Enter your username"
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="form-input"
                placeholder="Enter your password"
              />
            </div>

            <button type="submit" className="auth-button" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>

            <p className="auth-footer">
              <Link to="/forgot-password">Forgot Password?</Link>
            </p>
            <p className="auth-footer">
              Don't have an account? <Link to="/register">Register</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
};

export default Login;