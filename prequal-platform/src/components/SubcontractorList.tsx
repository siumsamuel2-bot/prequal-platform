import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { subcontractorApi, Subcontractor } from '../api/client';

const SubcontractorList = () => {
  const navigate = useNavigate();
  const [subcontractors, setSubcontractors] = useState<Subcontractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    const fetchSubcontractors = async () => {
      try {
        const data = await subcontractorApi.getAll();
        setSubcontractors(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load subcontractors');
      } finally {
        setLoading(false);
      }
    };
    fetchSubcontractors();
  }, []);

  const filteredSubcontractors = subcontractors.filter(sub => {
    const matchesSearch = 
      sub.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (sub.contact_first_name && sub.contact_first_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (sub.contact_last_name && sub.contact_last_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      sub.email.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || sub.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

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
            {filteredSubcontractors.length === 0 ? (
              <tr>
                <td colSpan={6}>No subcontractors found.</td>
              </tr>
            ) : (
              filteredSubcontractors.map(sub => (
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

      <div className="list-summary">
        Showing {filteredSubcontractors.length} of {subcontractors.length} subcontractors
      </div>
    </div>
  );
};

export default SubcontractorList;