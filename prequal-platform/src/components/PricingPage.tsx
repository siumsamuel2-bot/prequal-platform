import { Link } from 'react-router-dom';
import './PricingPage.css';

const PricingPage = () => {
  const plans = [
    {
      name: 'Starter',
      price: '$99',
      period: '/month',
      description: 'Perfect for small contractors just getting started.',
      features: [
        'Up to 25 subcontractors',
        'Basic compliance tracking',
        'Email alerts',
        'Standard reports',
        'Email support',
      ],
      cta: 'Start Free Trial',
      popular: false,
    },
    {
      name: 'Professional',
      price: '$249',
      period: '/month',
      description: 'For growing contractors managing multiple projects.',
      features: [
        'Up to 100 subcontractors',
        'Advanced compliance tracking',
        'SMS & email alerts',
        'Custom reports',
        'API access',
        'Priority support',
      ],
      cta: 'Start Free Trial',
      popular: true,
    },
    {
      name: 'Enterprise',
      price: '$499',
      period: '/month',
      description: 'For large teams with complex compliance needs.',
      features: [
        'Unlimited subcontractors',
        'Full compliance suite',
        'All alert channels',
        'Custom integrations',
        'Dedicated account manager',
        'SLA guarantee',
      ],
      cta: 'Contact Sales',
      popular: false,
    },
  ];

  const faqs = [
    {
      question: 'Can I change plans later?',
      answer: 'Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.',
    },
    {
      question: 'What payment methods do you accept?',
      answer: 'We accept all major credit cards, ACH transfers, and can invoice for annual contracts.',
    },
    {
      question: 'Is there a free trial?',
      answer: 'Yes! All plans come with a 14-day free trial. No credit card required.',
    },
    {
      question: 'What happens to my data if I cancel?',
      answer: 'You can export all your data at any time. After cancellation, data is retained for 30 days.',
    },
  ];

  return (
    <div className="pricing-page">
      <header className="pricing-header">
        <div className="pricing-header-content">
          <div className="logo">
            <Link to="/" className="logo-link">
              <span className="logo-icon">🛡️</span>
              <span className="logo-text">Prequal</span>
            </Link>
          </div>
          <nav className="pricing-nav">
            <Link to="/login" className="nav-link">Sign In</Link>
            <Link to="/register" className="nav-button">Get Started</Link>
          </nav>
        </div>
      </header>

      <section className="pricing-hero">
        <h1>Simple, Transparent Pricing</h1>
        <p>Choose the plan that fits your business. All plans include a 14-day free trial.</p>
      </section>

      <section className="pricing-plans">
        <div className="plans-grid">
          {plans.map((plan, index) => (
            <div key={index} className={`plan-card ${plan.popular ? 'popular' : ''}`}>
              {plan.popular && <span className="popular-badge">Most Popular</span>}
              <h3 className="plan-name">{plan.name}</h3>
              <div className="plan-price">
                <span className="price-amount">{plan.price}</span>
                <span className="price-period">{plan.period}</span>
              </div>
              <p className="plan-description">{plan.description}</p>
              <ul className="plan-features">
                {plan.features.map((feature, i) => (
                  <li key={i}>
                    <span className="check-icon">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`plan-cta ${plan.popular ? 'primary' : 'secondary'}`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="pricing-faq">
        <h2>Frequently Asked Questions</h2>
        <div className="faq-grid">
          {faqs.map((faq, index) => (
            <div key={index} className="faq-item">
              <h4>{faq.question}</h4>
              <p>{faq.answer}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="pricing-cta">
        <h2>Still Have Questions?</h2>
        <p>Talk to our team. We'll help you find the right plan for your business.</p>
        <Link to="/demo" className="cta-button">Request a Demo</Link>
      </section>

      <footer className="pricing-footer">
        <p>&copy; 2024 Prequal. All rights reserved. <Link to="/privacy">Privacy Policy</Link></p>
      </footer>
    </div>
  );
};

export default PricingPage;