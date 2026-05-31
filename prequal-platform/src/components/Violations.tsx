import { useState, useEffect } from 'react';
import { violationApi, Violation } from '../api/client';
import { Loading, EmptyState } from './Loading';
import { useToast } from './ToastContext';

const Violations = () => {
  const toast = useToast();
  const [violations, setViolations] = useState<Violation[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    const fetchViolations = async () => {
      try {
        const data = await violationApi.getAll();
        setViolations(data);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to load violations');
      } finally {
        setLoading(false);
      }
    };
    fetchViolations();
  }, [toast]);

  const uniqueViolationTypes = [...new Set(violations.map(v => v.violation_type))];

  const filteredViolations = violations.filter(v => {
    const matchesSearch = 
      v.violation_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (v.description && v.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
      v.subcontractor_id.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || v.status === statusFilter;
    const matchesType = typeFilter === 'all' || v.violation_type === typeFilter;
    
    return matchesSearch && matchesStatus && matchesType;
  });

  if (loading) return <div className="violations-page"><Loading message="Loading violations..." /></div>;

  return (
    <div className="violations-page">
      <h1>Violations</h1>
      
      <div className="page-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by type, description, or contractor..."
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
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="pending">Pending</option>
          </select>
        </div>

        <div className="filter-box">
          <label>Filter by type: </label>
          <select 
            value={typeFilter} 
            onChange={(e) => setTypeFilter(e.target.value)}
            className="type-select"
          >
            <option value="all">All Types</option>
            {uniqueViolationTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="violations-summary">
        <p>Total violations: {violations.length}</p>
        <p className="open-violations">
          Open violations: {violations.filter(v => v.status === 'open').length}
        </p>
      </div>

      <div className="violations-table">
        <table>
          <thead>
            <tr>
              <th>Violation Type</th>
              <th>Subcontractor ID</th>
              <th>Description</th>
              <th>Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredViolations.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <EmptyState
                    title={searchTerm || statusFilter !== 'all' || typeFilter !== 'all' ? 'No violations match your filters' : 'No violations recorded'}
                    description={searchTerm || statusFilter !== 'all' || typeFilter !== 'all' ? 'Try adjusting your search or filters.' : 'Violations will appear here when recorded.'}
                    icon={
                      <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    }
                  />
                </td>
              </tr>
            ) : (
              filteredViolations.map(v => (
                <tr key={v.id} className={v.status === 'open' ? 'open-violation' : ''}>
                  <td>{v.violation_type}</td>
                  <td>{v.subcontractor_id}</td>
                  <td className="description-cell">{v.description || 'N/A'}</td>
                  <td>{v.issued_date ? new Date(v.issued_date).toLocaleDateString() : 'N/A'}</td>
                  <td>
                    <span className={`status-badge ${v.status}`}>
                      {v.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="list-summary">
        Showing {filteredViolations.length} of {violations.length} violations
      </div>
    </div>
  );
};

export default Violations;