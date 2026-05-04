import React from 'react';
import SubcontractorProfile from './SubcontractorProfile';
import CertificationAlerts from './CertificationAlerts';
import CredentialUpload from './CredentialUpload';
import './Dashboard.css';

const Dashboard = () => {
  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Subcontractor Compliance Dashboard</h1>
        <nav className="dashboard-nav">
          <button className="nav-button active">Dashboard</button>
          <button className="nav-button">Reports</button>
          <button className="nav-button">Settings</button>
        </nav>
      </header>
      
      <div className="dashboard-content">
        <div className="dashboard-grid">
          <div className="dashboard-main">
            <SubcontractorProfile />
            <CertificationAlerts />
          </div>
          
          <div className="dashboard-sidebar">
            <CredentialUpload />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;