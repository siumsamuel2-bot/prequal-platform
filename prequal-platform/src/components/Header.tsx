import { useState } from 'react';
import './Header.css';

const Header = () => {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <header className="header">
      <div className="header-search">
        <input
          type="text"
          placeholder="Search subcontractors, certifications..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
      </div>
      <div className="header-actions">
        <button className="header-button notifications">
          <span className="notification-badge">3</span>
          Notifications
        </button>
        <div className="header-user">
          <span className="user-name">Admin User</span>
          <div className="user-avatar">AU</div>
        </div>
      </div>
    </header>
  );
};

export default Header;