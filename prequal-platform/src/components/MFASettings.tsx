import { useState, useEffect } from 'react';
import { authApi } from '../api/client';

export default function MFASettings() {
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'status' | 'enable' | 'verify' | 'backup'>('status');
  const [secret, setSecret] = useState('');
  const [otpauthUrl, setOtpauthUrl] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [tokenInput, setTokenInput] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    authApi.getMFAStatus().then(res => {
      setMfaEnabled(res.mfa_enabled);
    }).catch(() => {});
  }, []);

  const showMessage = (text: string, type: 'success' | 'error') => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleEnable = async () => {
    if (!password) {
      showMessage('Password required', 'error');
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const res = await authApi.enableMFA(password);
      setSecret(res.secret);
      setOtpauthUrl(res.otpauth_url);
      setStep('enable');
      showMessage('Scan the QR code with your authenticator app', 'success');
    } catch {
      showMessage('Failed to enable MFA', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!tokenInput) {
      showMessage('Token required', 'error');
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const res = await authApi.verifyMFA(tokenInput);
      setMfaEnabled(true);
      setPassword('');
      setTokenInput('');
      if (res.backup_codes && res.backup_codes.length > 0) {
        setBackupCodes(res.backup_codes);
        setStep('backup');
      } else {
        setStep('status');
        showMessage('MFA enabled successfully', 'success');
      }
    } catch {
      showMessage('Invalid token', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDisable = async () => {
    if (!password || !token) {
      showMessage('Password and token required', 'error');
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      await authApi.disableMFA(password, token);
      setMfaEnabled(false);
      setPassword('');
      setToken('');
      showMessage('MFA disabled', 'success');
    } catch {
      showMessage('Failed to disable MFA', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Two-Factor Authentication</h2>

      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {message.text}
        </div>
      )}

      {step === 'status' && (
        <div>
          <p className="text-gray-600 mb-4">
            Status: <span className={mfaEnabled ? 'text-green-600 font-medium' : 'text-gray-500'}>
              {mfaEnabled ? 'Enabled' : 'Disabled'}
            </span>
          </p>

          {!mfaEnabled ? (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">
                Enable two-factor authentication for enhanced security.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700">Confirm Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border px-3 py-2"
                />
              </div>
              <button
                onClick={handleEnable}
                disabled={loading}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Processing...' : 'Enable MFA'}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">
                Enter your password and a verification code to disable MFA.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Verification Code</label>
                <input
                  type="text"
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  placeholder="000000"
                  maxLength={6}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border px-3 py-2"
                />
              </div>
              <button
                onClick={handleDisable}
                disabled={loading}
                className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50"
              >
                {loading ? 'Processing...' : 'Disable MFA'}
              </button>
            </div>
          )}
        </div>
      )}

      {step === 'enable' && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.):
          </p>
          <div className="bg-gray-100 p-4 rounded">
            <img src={otpauthUrl} alt="MFA QR Code" className="mx-auto" style={{ maxWidth: '200px' }} />
          </div>
          <div className="text-sm">
            <p className="font-medium">Manual entry key:</p>
            <code className="bg-gray-100 px-2 py-1 rounded text-xs break-all">{secret}</code>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Verification Code</label>
            <input
              type="text"
              value={tokenInput}
              onChange={e => setTokenInput(e.target.value)}
              placeholder="000000"
              maxLength={6}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border px-3 py-2"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleVerify}
              disabled={loading}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? 'Verifying...' : 'Verify & Enable'}
            </button>
            <button
              onClick={() => setStep('status')}
              className="bg-gray-300 text-gray-700 px-4 py-2 rounded hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {step === 'backup' && (
        <div className="space-y-4">
          <div className="p-3 rounded bg-amber-100 text-amber-800 text-sm">
            Store these one-time backup codes somewhere safe. Each code can be used
            once instead of a verification code if you lose access to your
            authenticator. They will not be shown again.
          </div>
          <div className="grid grid-cols-2 gap-2">
            {backupCodes.map(code => (
              <code key={code} className="bg-gray-100 px-2 py-1 rounded text-sm text-center font-mono">
                {code}
              </code>
            ))}
          </div>
          <button
            onClick={() => {
              setBackupCodes([]);
              setStep('status');
              showMessage('MFA enabled successfully', 'success');
            }}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            I've saved my backup codes
          </button>
        </div>
      )}
    </div>
  );
}