import { Link } from 'react-router-dom';
import './LandingPage.css';

const LandingPage = () => {
  const features = [
    {
      icon: '📋',
      title: 'Certification Tracking',
      description: 'Track all subcontractor certifications in one place. Never miss an expiration again.',
    },
    {
      icon: '⚠️',
      title: 'Automated Alerts',
      description: 'Get notified before certifications expire. Reduce risk and stay compliant.',
    },
    {
      icon: '📊',
      title: 'Compliance Reports',
      description: 'Generate comprehensive compliance reports for any project in seconds.',
    },
    {
      icon: '🔒',
      title: 'Secure & Private',
      description: 'Enterprise-grade security. Your data is encrypted and protected.',
    },
  ];

  const testimonials = [
    {
      quote: 'Prequal saved us from multiple compliance issues. Our subs are now always up to date.',
      author: 'Mike Johnson',
      title: 'Project Manager, ABC Construction',
    },
    {
      quote: 'The automated alerts alone are worth it. We caught 3 expiring certs before they became problems.',
      author: 'Sarah Williams',
      title: 'Safety Director, BuildRight Inc',
    },
  ];

  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-header-content">
          <div className="logo">
            <span className="logo-icon">🛡️</span>
            <span className="logo-text">Prequal</span>
          </div>
          <nav className="landing-nav">
            <Link to="/login" className="nav-link">Sign In</Link>
            <Link to="/register" className="nav-button">Get Started Free</Link>
          </nav>
        </div>
      </header>

      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-title">
            Stop Chase. Start Track.
          </h1>
          <p className="hero-subtitle">
            Prequal automates subcontractor compliance tracking so you can focus on building.
            Never miss a certification expiration again.
          </p>
          <div className="hero-cta">
            <Link to="/register" className="cta-button primary">Start Free Trial</Link>
            <Link to="/demo" className="cta-button secondary">Request Demo</Link>
          </div>
          <div className="hero-trust">
            <span>Trusted by 200+ contractors</span>
            <span>•</span>
            <span>No credit card required</span>
          </div>
        </div>
      </section>

      <section className="features">
        <div className="section-header">
          <h2>Everything You Need to Stay Compliant</h2>
          <p>Powerful features that work together to keep your subcontractors on track.</p>
        </div>
        <div className="features-grid">
          {features.map((feature, index) => (
            <div key={index} className="feature-card">
              <span className="feature-icon">{feature.icon}</span>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="social-proof">
        <div className="section-header">
          <h2>Trusted by Construction Leaders</h2>
        </div>
        <div className="testimonials-grid">
          {testimonials.map((testimonial, index) => (
            <div key={index} className="testimonial-card">
              <p className="testimonial-quote">"{testimonial.quote}"</p>
              <div className="testimonial-author">
                <strong>{testimonial.author}</strong>
                <span>{testimonial.title}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="cta-section">
        <div className="cta-content">
          <h2>Ready to Get Started?</h2>
          <p>Join hundreds of contractors who trust Prequal for compliance tracking.</p>
          <Link to="/register" className="cta-button primary">Start Your Free Trial</Link>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="logo">
              <span className="logo-icon">🛡️</span>
              <span className="logo-text">Prequal</span>
            </div>
            <p>Subcontractor compliance tracking for construction professionals.</p>
          </div>
          <div className="footer-links">
            <div className="footer-column">
              <h4>Product</h4>
              <Link to="/pricing">Pricing</Link>
              <Link to="/features">Features</Link>
              <Link to="/demo">Request Demo</Link>
            </div>
            <div className="footer-column">
              <h4>Company</h4>
              <Link to="/about">About</Link>
              <Link to="/contact">Contact</Link>
              <Link to="/privacy">Privacy Policy</Link>
            </div>
            <div className="footer-column">
              <h4>Resources</h4>
              <Link to="/compliance-guide">Compliance Guide</Link>
              <Link to="/blog">Blog</Link>
              <Link to="/help">Help Center</Link>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; 2024 Prequal. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;