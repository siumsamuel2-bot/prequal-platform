import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { subcontractorApi, Subcontractor } from '../api/client';

const PAGE_SIZE = 20;

const SubcontractorList = () => {
  const navigate = useNavigate();
  const [allSubcontractors, setAllSubcontractors] = useState<Subcontractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(0);

  useEffect(() => {
    const fetchSubcontractors = async () => {
      setLoading(true);
      try {
        const data = await subcontractorApi.getAll();
        setAllSubcontractors(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load subcontractors');
      } finally {
        setLoading(false);
      }
    };
    fetchSubcontractors();
  }, []);

  const filteredSubcontractors = useMemo(() => {
    return allSubcontractors.filter(sub => {
      const matchesSearch = 
        sub.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (sub.contact_first_name && sub.contact_first_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (sub.contact_last_name && sub.contact_last_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
        sub.email.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesStatus = statusFilter === 'all' || sub.status === statusFilter;
      
      return matchesSearch && matchesStatus;
    });
  }, [allSubcontractors, searchTerm, statusFilter]);

  const totalCount = filteredSubcontractors.length;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const paginatedSubcontractors = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filteredSubcontractors.slice(start, start + PAGE_SIZE);
  }, [filteredSubcontractors, page]);

  const handleViewProfile = (id: string) => {
    navigate(`/subcontractors/${id}`);
  };

  const handleAddNew = () => {
    navigate('/subcontractors/new');
  };

  if (loading) return <div className="subcontractor-list">Loading subcontractors...</div>;
  if (error) return <div className="subcontractor-list error">{error}</div>;

  return (
    <div className="subcontractor-list">
      <div className="list-header">
        <h1>Subcontractors</h1>
        <button className="add-btn" onClick={handleAddNew}>+ Add Subcontractor</button>
      </div>
      
      <div className="list-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by company, contact, or email..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
            className="search-input"
          />
        </div>
        
        <div className="filter-box">
          <label>Filter by status: </label>
          <select 
            value={statusFilter} 
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            className="status-select"
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
            <option value="blacklisted">Blacklisted</option>
          </select>
        </div>
      </div>

      <div className="subcontractors-table">
        <table>
          <thead>
            <tr>
              <th>Company Name</th>
              <th>Contact</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginatedSubcontractors.length === 0 ? (
              <tr>
                <td colSpan={6}>No subcontractors found.</td>
              </tr>
            ) : (
              paginatedSubcontractors.map(sub => (
                <tr key={sub.id}>
                  <td>{sub.company_name}</td>
                  <td>{sub.contact_first_name} {sub.contact_last_name}</td>
                  <td>{sub.email}</td>
                  <td>{sub.phone}</td>
                  <td>
                    <span className={`status-badge ${sub.status}`}>
                      {sub.status}
                    </span>
                  </td>
                  <td>
                    <button className="view-btn" onClick={() => handleViewProfile(sub.id)}>View Profile</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button 
            className="pagination-btn" 
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            Previous
          </button>
          <span className="pagination-info">Page {page + 1} of {totalPages}</span>
          <button 
            className="pagination-btn" 
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            Next
          </button>
        </div>
      )}

      <div className="list-summary">
        Showing {paginatedSubcontractors.length} of {totalCount} subcontractors
      </div>
    </div>
  );
};

export default SubcontractorList;