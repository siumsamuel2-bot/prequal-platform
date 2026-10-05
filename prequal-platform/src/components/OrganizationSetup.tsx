import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import './OrganizationSetup.css';

export const OrganizationSetup = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [orgName, setOrgName] = useState('');
  const [slug, setSlug] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleNameChange = (name: string) => {
    setOrgName(name);
    const generatedSlug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    setSlug(generatedSlug);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await apiClient.post('/auth/organizations', { name: orgName, slug });
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create organization');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="onboarding-container">
      <div className="onboarding-card">
        <div className="onboarding-progress">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>1</div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>2</div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>3</div>
        </div>

        {step === 1 && (
          <div className="step-content">
            <h1 className="onboarding-title">Welcome to Prequal!</h1>
            <p className="onboarding-subtitle">Let's set up your organization to get started.</p>
            <div className="feature-list">
              <div className="feature-item">
                <span className="feature-icon">📋</span>
                <span>Track subcontractor certifications and compliance</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">⚠️</span>
                <span>Get alerts for expiring certifications</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">📊</span>
                <span>Generate compliance reports</span>
              </div>
            </div>
            <button className="onboarding-button" onClick={() => setStep(2)}>
              Get Started
            </button>
          </div>
        )}

        {step === 2 && (
          <form onSubmit={handleSubmit} className="step-content">
            <h1 className="onboarding-title">Set Up Your Organization</h1>
            <p className="onboarding-subtitle">This will be your company's workspace in Prequal.</p>

            {error && <div className="onboarding-error">{error}</div>}

            <div className="form-group">
              <label htmlFor="orgName">Organization Name</label>
              <input
                type="text"
                id="orgName"
                value={orgName}
                onChange={(e) => handleNameChange(e.target.value)}
                required
                className="form-input"
                placeholder="e.g., Acme Construction"
              />
            </div>

            <div className="form-group">
              <label htmlFor="slug">URL Slug</label>
              <input
                type="text"
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                className="form-input"
                placeholder="acme-construction"
              />
              <span className="form-hint">This will be used in your organization's URL</span>
            </div>

            <div className="onboarding-actions">
              <button type="button" className="onboarding-button secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="submit" className="onboarding-button" disabled={isLoading || !orgName || !slug}>
                {isLoading ? 'Creating...' : 'Create Organization'}
              </button>
            </div>
          </form>
        )}

        {step === 3 && (
          <div className="step-content">
            <div className="success-icon">✓</div>
            <h1 className="onboarding-title">You're All Set!</h1>
            <p className="onboarding-subtitle">Your organization has been created. Let's add your first subcontractor.</p>
            <div className="onboarding-actions">
              <button className="onboarding-button" onClick={() => navigate('/subcontractors/new')}>
                Add First Subcontractor
              </button>
              <button className="onboarding-button secondary" onClick={() => navigate('/dashboard')}>
                Go to Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OrganizationSetup;