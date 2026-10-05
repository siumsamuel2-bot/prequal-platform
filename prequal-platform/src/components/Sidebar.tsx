import { Link, useLocation } from 'react-router-dom';
import { logout } from '../utils/auth';
import './Sidebar.css';

const Sidebar = () => {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;
  const isAnalyticsActive = () => location.pathname.startsWith('/analytics');

  const handleLogout = () => {
    logout();
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2 className="sidebar-logo">Prequal</h2>
      </div>
      <nav className="sidebar-nav">
        <Link
          to="/dashboard"
          className={`sidebar-link ${isActive('/dashboard') ? 'active' : ''}`}
        >
          Dashboard
        </Link>
        <Link
          to="/compliance-dashboard"
          className={`sidebar-link ${isActive('/compliance-dashboard') ? 'active' : ''}`}
        >
          Compliance Dashboard
        </Link>
        <Link
          to="/analytics-dashboard"
          className={`sidebar-link ${isActive('/analytics-dashboard') ? 'active' : ''}`}
        >
          Analytics Dashboard
        </Link>
        <Link
          to="/analytics/pilot-engagement"
          className={`sidebar-link ${isAnalyticsActive() ? 'active' : ''}`}
        >
          Analytics Hub
        </Link>
        <Link
          to="/subcontractors"
          className={`sidebar-link ${isActive('/subcontractors') ? 'active' : ''}`}
        >
          Subcontractors
        </Link>
        <Link
          to="/certifications"
          className={`sidebar-link ${isActive('/certifications') ? 'active' : ''}`}
        >
          Certifications
        </Link>
        <Link
          to="/violations"
          className={`sidebar-link ${isActive('/violations') ? 'active' : ''}`}
        >
          Violations
        </Link>
        <Link
          to="/reports"
          className={`sidebar-link ${isActive('/reports') ? 'active' : ''}`}
        >
          Reports
        </Link>
        <Link
          to="/settings"
          className={`sidebar-link ${isActive('/settings') ? 'active' : ''}`}
        >
          Settings
        </Link>
      </nav>
      <div className="sidebar-footer">
        <button onClick={handleLogout} className="sidebar-logout">Logout</button>
      </div>
    </aside>
  );
};

export default Sidebar;