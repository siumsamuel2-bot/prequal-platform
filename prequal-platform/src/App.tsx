import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import Login from './components/Login';
import Register from './components/Register';
import ForgotPassword from './components/ForgotPassword';
import ResetPassword from './components/ResetPassword';
import SubcontractorList from './components/SubcontractorList';
import SubcontractorProfile from './components/SubcontractorProfile';
import Certifications from './components/Certifications';
import Violations from './components/Violations';
import NotFound from './components/NotFound';
import { isAuthenticated } from './utils/auth';
import { ToastProvider } from './components/ToastContext';
import { ToastContainer } from './components/ToastContainer';
import { ErrorBoundary } from './components/ErrorBoundary';

const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppContent = () => {
  return (
    <Routes>
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
                <Route path="/subcontractors" element={<SubcontractorList />} />
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