import SubcontractorProfile from './SubcontractorProfile';
import CertificationAlerts from './CertificationAlerts';
import CredentialUpload from './CredentialUpload';
import './Dashboard.css';

const Dashboard = () => {
  return (
    <div className="dashboard">
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
  );
};

export default Dashboard;