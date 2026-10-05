import { useState } from 'react';
import './Header.css';

interface HeaderProps {
  onFeedbackClick?: () => void;
}

const Header = ({ onFeedbackClick }: HeaderProps) => {
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
        <button className="header-button feedback-btn" onClick={onFeedbackClick}>
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          Feedback
        </button>
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