import { useState, useEffect } from 'react';
import { complianceApi, ComplianceAlert } from '../api/client';

interface Alert extends ComplianceAlert {
  days_until?: number;
}

const CertificationAlerts = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const data = await complianceApi.getAlerts();
        setAlerts(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load alerts');
      } finally {
        setLoading(false);
      }
    };
    fetchAlerts();
  }, []);

  const handleDismiss = (alertId: string) => {
    setDismissedIds(prev => new Set([...prev, alertId]));
  };

  const visibleAlerts = alerts.filter(alert => !dismissedIds.has(alert.id?.toString() || ''));

  if (loading) {
    return (
      <div className="certification-alerts">
        <h2>Certification Alerts</h2>
        <div className="alerts-loading">Loading alerts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="certification-alerts">
        <h2>Certification Alerts</h2>
        <div className="alerts-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="certification-alerts">
      <h2>Certification Alerts</h2>
      
      {visibleAlerts.length === 0 ? (
        <div className="alerts-empty">
          <span className="no-alerts">No active alerts</span>
        </div>
      ) : (
        <div className="alerts-list">
          {visibleAlerts.map((alert, index) => (
            <div 
              key={`${alert.id}-${index}`} 
              className={`alert-item ${alert.type}`}
            >
              <div className="alert-content">
                <span className={`alert-badge ${alert.type}`}>
                  {alert.type?.toUpperCase() || 'WARNING'}
                </span>
                <span className="alert-message">{alert.message}</span>
                {alert.expiration_date && (
                  <span className="alert-expiration">
                    Expires: {new Date(alert.expiration_date).toLocaleDateString()}
                  </span>
                )}
              </div>
              <div className="alert-actions">
                <button className="view-btn">View</button>
                <button 
                  className="dismiss-btn"
                  onClick={() => handleDismiss(alert.id?.toString() || '')}
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CertificationAlerts;