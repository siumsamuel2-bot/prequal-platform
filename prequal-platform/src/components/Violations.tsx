import { useState, useEffect } from 'react';
import { violationApi, Violation } from '../api/client';

const Violations = () => {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    const fetchViolations = async () => {
      try {
        const data = await violationApi.getAll();
        setViolations(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load violations');
      } finally {
        setLoading(false);
      }
    };
    fetchViolations();
  }, []);

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

  if (loading) return <div className="violations-page">Loading violations...</div>;
  if (error) return <div className="violations-page error">{error}</div>;

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
                <td colSpan={5}>No violations found.</td>
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