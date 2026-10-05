import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import './DemoRequest.css';

interface DemoFormData {
  name: string;
  company: string;
  email: string;
  phone: string;
  companySize: string;
  message: string;
}

export const DemoRequest = () => {
  const [formData, setFormData] = useState<DemoFormData>({
    name: '',
    company: '',
    email: '',
    phone: '',
    companySize: '',
    message: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setSubmitted(true);
    setIsSubmitting(false);
  };

  if (submitted) {
    return (
      <div className="demo-page">
        <div className="demo-success">
          <div className="success-icon">✓</div>
          <h1>Thanks for Your Interest!</h1>
          <p>Our team will reach out within 24 hours to schedule your personalized demo.</p>
          <Link to="/" className="back-link">Back to Home</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="demo-page">
      <header className="demo-header">
        <Link to="/" className="logo-link">
          <span className="logo-icon">🛡️</span>
          <span className="logo-text">Prequal</span>
        </Link>
      </header>

      <div className="demo-content">
        <div className="demo-info">
          <h1>See Prequal in Action</h1>
          <p>Schedule a personalized demo with our team. We'll show you how Prequal can streamline your subcontractor compliance tracking.</p>
          <ul className="demo-benefits">
            <li>
              <span className="benefit-icon">✓</span>
              Personalized walkthrough tailored to your workflows
            </li>
            <li>
              <span className="benefit-icon">✓</span>
              See how to migrate from spreadsheets in under 5 minutes
            </li>
            <li>
              <span className="benefit-icon">✓</span>
              Get pricing tailored to your team size
            </li>
            <li>
              <span className="benefit-icon">✓</span>
              Ask any questions you have
            </li>
          </ul>
        </div>

        <form className="demo-form" onSubmit={handleSubmit}>
          <h2>Request Your Demo</h2>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                placeholder="John Smith"
              />
            </div>
            <div className="form-group">
              <label htmlFor="company">Company</label>
              <input
                type="text"
                id="company"
                name="company"
                value={formData.company}
                onChange={handleChange}
                required
                placeholder="ABC Construction"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="email">Work Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                placeholder="john@abcconstruction.com"
              />
            </div>
            <div className="form-group">
              <label htmlFor="phone">Phone</label>
              <input
                type="tel"
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="(555) 123-4567"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="companySize">Company Size</label>
            <select
              id="companySize"
              name="companySize"
              value={formData.companySize}
              onChange={handleChange}
              required
            >
              <option value="">Select company size</option>
              <option value="1-10">1-10 employees</option>
              <option value="11-50">11-50 employees</option>
              <option value="51-200">51-200 employees</option>
              <option value="201+">201+ employees</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="message">Anything else you'd like us to know?</label>
            <textarea
              id="message"
              name="message"
              value={formData.message}
              onChange={handleChange}
              rows={4}
              placeholder="Tell us about your current compliance tracking process..."
            />
          </div>

          <button type="submit" className="submit-button" disabled={isSubmitting}>
            {isSubmitting ? 'Submitting...' : 'Request Demo'}
          </button>

          <p className="form-disclaimer">
            By submitting, you agree to our Privacy Policy. We'll never share your information.
          </p>
        </form>
      </div>
    </div>
  );
};

export default DemoRequest;