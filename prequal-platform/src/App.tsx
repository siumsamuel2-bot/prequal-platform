import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import Login from './components/Login';
import Register from './components/Register';
import SubcontractorList from './components/SubcontractorList';
import SubcontractorProfile from './components/SubcontractorProfile';
import Certifications from './components/Certifications';
import Violations from './components/Violations';
import { isAuthenticated } from './utils/auth';

const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
};

const App = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
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
              </Routes>
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  );
};

export default App;