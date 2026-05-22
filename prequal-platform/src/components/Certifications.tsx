import { useState, useEffect } from 'react';
import { certificationApi, Certification } from '../api/client';
import { Loading, EmptyState } from './Loading';

const Certifications = () => {
  const [certifications, setCertifications] = useState<Certification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    const fetchCertifications = async () => {
      try {
        const data = await certificationApi.getAll();
        setCertifications(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load certifications');
      } finally {
        setLoading(false);
      }
    };
    fetchCertifications();
  }, []);

  const filteredCertifications = certifications.filter(cert => {
    const matchesSearch = 
      cert.certification_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cert.subcontractor_id.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || cert.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const isExpiringSoon = (expiryDate: string) => {
    const expiry = new Date(expiryDate);
    const today = new Date();
    const daysUntilExpiry = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    return daysUntilExpiry <= 30 && daysUntilExpiry > 0;
  };

  const isExpired = (expiryDate: string) => {
    return new Date(expiryDate) < new Date();
  };

  if (loading) return <div className="certifications-page"><Loading message="Loading certifications..." /></div>;
  if (error) return <div className="certifications-page error">{error}</div>;

  return (
    <div className="certifications-page">
      <h1>Certifications</h1>
      
      <div className="page-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by type or contractor..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        
        <div className="filter-box">
          <label>Filter by status: </label>
          <select 
            value={statusFilter} 
            onChange={(e) => setStatusFilter(e.target.value)}
            className="status-select"
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      <div className="certifications-summary">
        <p>Total certifications: {certifications.length}</p>
        <p className="expiring-soon">
          Expiring within 30 days: {certifications.filter(c => isExpiringSoon(c.expiration_date)).length}
        </p>
      </div>

      <div className="certifications-table">
        <table>
          <thead>
            <tr>
              <th>Certification Type</th>
              <th>Contractor ID</th>
              <th>Issue Date</th>
              <th>Expiry Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredCertifications.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <EmptyState
                    title={searchTerm || statusFilter !== 'all' ? 'No certifications match your filters' : 'No certifications yet'}
                    description={searchTerm || statusFilter !== 'all' ? 'Try adjusting your search or filters.' : 'Upload credentials to see certifications here.'}
                    icon={
                      <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                      </svg>
                    }
                  />
                </td>
              </tr>
            ) : (
              filteredCertifications.map(cert => {
                const expired = isExpired(cert.expiration_date);
                const expiringSoon = isExpiringSoon(cert.expiration_date);
                return (
                  <tr key={cert.id} className={expired ? 'expired' : expiringSoon ? 'expiring-soon' : ''}>
                    <td>{cert.certification_type}</td>
                    <td>{cert.subcontractor_id}</td>
                    <td>{cert.issue_date ? new Date(cert.issue_date).toLocaleDateString() : 'N/A'}</td>
                    <td>{new Date(cert.expiration_date).toLocaleDateString()}</td>
                    <td>
                      <span className={`status-badge ${expired ? 'expired' : expiringSoon ? 'warning' : cert.status}`}>
                        {expired ? 'Expired' : expiringSoon ? 'Expiring Soon' : cert.status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="list-summary">
        Showing {filteredCertifications.length} of {certifications.length} certifications
      </div>
    </div>
  );
};

export default Certifications;