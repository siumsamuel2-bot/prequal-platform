import { useState, useEffect } from 'react';
import { billingApi, SubscriptionStatus } from '../api/client';
import './BillingSettings.css';

interface Plan {
  plan: string;
  name: string;
  price: string;
  limit: number;
  features: string[];
}

export const BillingSettings = () => {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [plansData, subData] = await Promise.all([
          billingApi.getPlans(),
          billingApi.getSubscription()
        ]);
        setPlans(plansData);
        setSubscription(subData);
      } catch (err) {
        console.error('Failed to fetch billing data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSubscribe = async (plan: string) => {
    setProcessing(plan);
    setMessage(null);
    try {
      const response = await billingApi.createCheckout(plan);
      window.location.href = response.checkout_url;
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to start checkout. Please try again.' });
      setProcessing(null);
    }
  };

  const handleManageBilling = async () => {
    setProcessing('portal');
    setMessage(null);
    try {
      const response = await billingApi.createPortal();
      window.location.href = response.portal_url;
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to open billing portal. Please try again.' });
      setProcessing(null);
    }
  };

  if (loading) {
    return <div className="billing-loading">Loading billing information...</div>;
  }

  const currentPlan = plans.find(p => p.plan === subscription?.plan);

  return (
    <div className="billing-settings">
      <h1>Billing & Subscription</h1>

      {message && (
        <div className={`billing-message ${message.type}`}>
          {message.text}
        </div>
      )}

      {subscription && subscription.status !== 'inactive' && (
        <div className="current-subscription">
          <h2>Current Plan</h2>
          <div className="subscription-card">
            <div className="subscription-info">
              <span className="plan-name">{currentPlan?.name || subscription.plan}</span>
              <span className={`status-badge ${subscription.status}`}>{subscription.status}</span>
            </div>
            <div className="subscription-details">
              <p>
                <strong>{subscription.subcontractor_count}</strong> / {subscription.subcontractor_limit === -1 ? '∞' : subscription.subcontractor_limit} subcontractors
              </p>
              {subscription.current_period_end && (
                <p>Renews: {new Date(subscription.current_period_end).toLocaleDateString()}</p>
              )}
            </div>
            <button
              className="manage-button"
              onClick={handleManageBilling}
              disabled={processing === 'portal'}
            >
              {processing === 'portal' ? 'Opening...' : 'Manage Billing'}
            </button>
          </div>
        </div>
      )}

      <div className="plans-section">
        <h2>Available Plans</h2>
        <div className="plans-grid">
          {plans.map((plan) => (
            <div
              key={plan.plan}
              className={`plan-card ${subscription?.plan === plan.plan ? 'current' : ''}`}
            >
              {subscription?.plan === plan.plan && (
                <span className="current-badge">Current Plan</span>
              )}
              <h3>{plan.name}</h3>
              <div className="plan-price">{plan.price}</div>
              <ul className="plan-features">
                {plan.features.map((feature, index) => (
                  <li key={index}>✓ {feature}</li>
                ))}
              </ul>
              {subscription?.plan === plan.plan ? (
                <button className="plan-button current" disabled>
                  Current Plan
                </button>
              ) : (
                <button
                  className="plan-button"
                  onClick={() => handleSubscribe(plan.plan)}
                  disabled={processing !== null}
                >
                  {processing === plan.plan ? 'Processing...' : `Subscribe to ${plan.name}`}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default BillingSettings;