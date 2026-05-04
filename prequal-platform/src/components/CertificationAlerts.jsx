import React, { useState } from 'react';

const CertificationAlerts = () => {
  const [alerts, setAlerts] = useState([
    { id: 1, type: 'critical', message: 'Certification expiring in 30 days', status: 'active' },
    { id: 2, type: 'warning', message: 'Documentation requires verification', status: 'pending' }
  ]);

  const dismissAlert = (id) => {
    setAlerts(alerts.filter(alert => alert.id !== id));
  };

  return (
    <div className="certification-alerts">
      <h2>Certification Alerts</h2>
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
    </div>
  );
};

export default CertificationAlerts;