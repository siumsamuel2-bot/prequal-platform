import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import PerformanceDashboard from './components/PerformanceDashboard';
import ComplianceDashboard from './components/ComplianceDashboard';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import AnalyticsHub from './components/analytics/AnalyticsHub';
import Login from './components/Login';
import Register from './components/Register';
import ForgotPassword from './components/ForgotPassword';
import ResetPassword from './components/ResetPassword';
import SubcontractorList from './components/SubcontractorList';
import SubcontractorProfile from './components/SubcontractorProfile';
import SubcontractorImportWizard from './components/SubcontractorImportWizard';
import Certifications from './components/Certifications';
import Violations from './components/Violations';
import NotFound from './components/NotFound';
import { isAuthenticated } from './utils/auth';
import { ToastProvider } from './components/ToastContext';
import { ToastContainer } from './components/ToastContainer';
import { ErrorBoundary } from './components/ErrorBoundary';
import OrganizationSetup from './components/OrganizationSetup';
import LandingPage from './components/LandingPage';
import PricingPage from './components/PricingPage';
import DemoRequest from './components/DemoRequest';
import LeadMagnet from './components/LeadMagnet';
import BillingSettings from './components/BillingSettings';
import MFASettings from './components/MFASettings';
import SupportPage from './components/SupportPage';
import AdminFeedbackReview from './components/AdminFeedbackReview';
import { useAnalytics } from './hooks/useAnalytics';

const PAGE_NAME_MAP: Record<string, string> = {
  '/': 'dashboard',
  '/dashboard': 'dashboard',
  '/performance-dashboard': 'performance_dashboard',
  '/compliance-dashboard': 'compliance_dashboard',
  '/analytics-dashboard': 'analytics_dashboard',
  '/analytics/pilot-engagement': 'analytics_pilot_engagement',
  '/analytics/compliance': 'analytics_compliance',
  '/analytics/subcontractors': 'analytics_subcontractors',
  '/analytics/system-health': 'analytics_system_health',
  '/setup': 'organization_setup',
  '/settings/billing': 'billing_settings',
  '/settings/mfa': 'mfa_settings',
  '/support': 'support',
  '/admin/feedback': 'admin_feedback_review',
  '/subcontractors': 'subcontractor_list',
  '/subcontractors/import': 'subcontractor_import',
  '/certifications': 'certifications',
  '/violations': 'violations',
};

const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppContent = () => {
  const location = useLocation();
  const { trackPageView, trackFeatureUsage } = useAnalytics();

  useEffect(() => {
    const pageName = PAGE_NAME_MAP[location.pathname] || location.pathname.replace(/\//g, '_').replace(/^_/, '') || 'unknown';
    trackPageView(location.pathname, document.referrer || undefined);
    trackFeatureUsage(pageName, { referrer: document.referrer || undefined });
  }, [location.pathname, trackPageView, trackFeatureUsage]);

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route path="/demo" element={<DemoRequest />} />
      <Route path="/compliance-guide" element={<LeadMagnet />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/*"
        element={
          <PrivateRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/performance-dashboard" element={<PerformanceDashboard />} />
                <Route path="/compliance-dashboard" element={<ComplianceDashboard />} />
                <Route path="/analytics-dashboard" element={<AnalyticsDashboard />} />
                <Route path="/analytics/*" element={<AnalyticsHub />} />
                <Route path="/setup" element={<OrganizationSetup />} />
                <Route path="/settings/billing" element={<BillingSettings />} />
                <Route path="/settings/mfa" element={<MFASettings />} />
                <Route path="/support" element={<SupportPage />} />
                <Route path="/admin/feedback" element={<AdminFeedbackReview />} />
                <Route path="/subcontractors" element={<SubcontractorList />} />
                <Route path="/subcontractors/import" element={<SubcontractorImportWizard />} />
                <Route path="/subcontractors/:id" element={<SubcontractorProfile />} />
                <Route path="/certifications" element={<Certifications />} />
                <Route path="/violations" element={<Violations />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  );
};

const App = () => {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AppContent />
        <ToastContainer />
      </ToastProvider>
    </ErrorBoundary>
  );
};

export default App;