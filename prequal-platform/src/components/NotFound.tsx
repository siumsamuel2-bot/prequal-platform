import { Link } from 'react-router-dom';

const NotFound = () => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      textAlign: 'center',
      padding: '2rem'
    }}>
      <div style={{
        fontSize: '72px',
        fontWeight: '700',
        color: '#3b82f6',
        lineHeight: 1,
        marginBottom: '1rem'
      }}>
        404
      </div>
      <h1 style={{
        fontSize: '24px',
        fontWeight: '600',
        color: '#111827',
        marginBottom: '0.5rem'
      }}>
        Page Not Found
      </h1>
      <p style={{
        fontSize: '14px',
        color: '#6b7280',
        marginBottom: '1.5rem',
        maxWidth: '400px'
      }}>
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/dashboard"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 20px',
          backgroundColor: '#3b82f6',
          color: 'white',
          borderRadius: '6px',
          textDecoration: 'none',
          fontSize: '14px',
          fontWeight: '500'
        }}
      >
        Go to Dashboard
      </Link>
    </div>
  );
};

export default NotFound;