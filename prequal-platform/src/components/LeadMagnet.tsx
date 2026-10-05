import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import './LeadMagnet.css';

export const LeadMagnet = () => {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setSubmitted(true);
    setIsSubmitting(false);
  };

  if (submitted) {
    return (
      <div className="lead-magnet-page">
        <div className="lead-success">
          <div className="success-icon">✓</div>
          <h1>You're In!</h1>
          <p>Check your email for the Compliance Checklist PDF. We've also included some bonus tips to get you started.</p>
          <Link to="/register" className="cta-button">Start Your Free Trial</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="lead-magnet-page">
      <header className="lead-header">
        <Link to="/" className="logo-link">
          <span className="logo-icon">🛡️</span>
          <span className="logo-text">Prequal</span>
        </Link>
      </header>

      <div className="lead-content">
        <div className="lead-book">
          <div className="book-cover">
            <span className="book-icon">📋</span>
            <span className="book-badge">FREE GUIDE</span>
          </div>
        </div>

        <div className="lead-info">
          <h1>The Subcontractor Compliance Checklist Every GC Needs</h1>
          <p className="lead-subtitle">
            Download our comprehensive 15-point compliance checklist used by top GCs to eliminate certification gaps and reduce risk on every project.
          </p>

          <ul className="checklist-preview">
            <li>✓ OSHA certification tracking best practices</li>
            <li>✓ State licensing verification procedures</li>
            <li>✓ Insurance certificate management tips</li>
            <li>✓ Annual audit checklist template</li>
          </ul>

          <form className="lead-form" onSubmit={handleSubmit}>
            <label htmlFor="email">Get your free compliance checklist</label>
            <div className="email-input-group">
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your work email"
                required
              />
              <button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Sending...' : 'Get Free Checklist'}
              </button>
            </div>
            <p className="form-disclaimer">We'll also send you occasional tips. Unsubscribe anytime.</p>
          </form>

          <div className="trust-badges">
            <span>🔒 No spam, ever</span>
            <span>📧 Sent within 5 minutes</span>
          </div>
        </div>
      </div>

      <div className="lead-footer">
        <p>Join 2,000+ construction professionals who trust Prequal for compliance tracking.</p>
        <Link to="/register">Start Free Trial</Link>
      </div>
    </div>
  );
};

export default LeadMagnet;