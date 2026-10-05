import { useState, ReactNode } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import Breadcrumb from './Breadcrumb';
import { FeedbackModal } from './FeedbackModal';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
  const [showFeedback, setShowFeedback] = useState(false);

  return (
    <div className="layout">
      <Sidebar />
      <div className="layout-main">
        <Header onFeedbackClick={() => setShowFeedback(true)} />
        <div className="layout-content">
          <Breadcrumb />
          {children}
        </div>
      </div>
      <FeedbackModal isOpen={showFeedback} onClose={() => setShowFeedback(false)} />
    </div>
  );
};

export default Layout;