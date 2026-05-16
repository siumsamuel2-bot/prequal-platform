import React, { useState, useEffect } from 'react';
import { complianceApi } from '../api/client';

const CertificationAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const dismissAlert = (id) => {
    setAlerts(alerts.filter(alert => alert.id !== id));
  };

  if (loading) return <div className="certification-alerts">Loading alerts...</div>;
  if (error) return <div className="certification-alerts error">{error}</div>;

  return (
    <div className="certification-alerts">
      <h2>Certification Alerts</h2>
      {alerts.length === 0 ? (
        <p>No alerts at this time.</p>
      ) : (
        <div className="alerts-list">
          {alerts.map(alert => (
            <div key={alert.id} className="alert-item">
              <span className={`alert-status ${alert.type}`}>
                {alert.type.charAt(0).toUpperCase() + alert.type.slice(1)}
              </span>
              <span>{alert.message}</span>
              <button onClick={() => dismissAlert(alert.id)}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CertificationAlerts;