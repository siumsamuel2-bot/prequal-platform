import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { subcontractorApi, certificationApi, violationApi, Subcontractor, Certification, Violation } from '../api/client';
import DocumentUpload from './DocumentUpload';
import { Loading } from './Loading';

const SubcontractorProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [subcontractor, setSubcontractor] = useState<Subcontractor | null>(null);
  const [certifications, setCertifications] = useState<Certification[]>([]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'details' | 'certifications' | 'violations'>('details');

  const isNew = id === 'new';

  useEffect(() => {
    const fetchData = async () => {
      if (isNew) {
        setSubcontractor({
          id: '',
          company_name: '',
          email: '',
          phone: '',
          status: 'active',
          contact_first_name: '',
          contact_last_name: ''
        } as Subcontractor);
        setLoading(false);
        return;
      }

      if (!id) return;

      try {
        const [subData, certsData, violationsData] = await Promise.all([
          subcontractorApi.getById(id),
          certificationApi.getAll().then(certs => certs.filter(c => c.subcontractor_id === id)),
          violationApi.getAll().then(v => v.filter(v => v.subcontractor_id === id))
        ]);
        setSubcontractor(subData);
        setCertifications(certsData);
        setViolations(violationsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load subcontractor');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id, isNew]);

  const handleChange = (field: keyof Subcontractor, value: string) => {
    if (subcontractor) {
      setSubcontractor({ ...subcontractor, [field]: value });
    }
  };

  const handleSave = async () => {
    if (!subcontractor) return;

    setSaving(true);
    setSaveSuccess(false);

    try {
      if (isNew) {
        const created = await subcontractorApi.create(subcontractor);
        setSaveSuccess(true);
        setTimeout(() => navigate(`/subcontractors/${created.id}`), 1500);
      } else {
        await subcontractorApi.update(subcontractor.id, subcontractor);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate('/subcontractors');
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'valid': return 'status-valid';
      case 'expired': return 'status-expired';
      case 'open': return 'status-open';
      case 'resolved': return 'status-resolved';
      default: return '';
    }
  };

  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="subcontractor-profile">
        <Loading message="Loading profile..." fullScreen={false} />
      </div>
    );
  }

  if (error && !subcontractor) {
    return (
      <div className="subcontractor-profile">
        <div className="profile-error">{error}</div>
        <button onClick={() => navigate('/subcontractors')}>Back to List</button>
      </div>
    );
  }

  if (!subcontractor) return null;

  return (
    <div className="subcontractor-profile">
      <div className="profile-header">
        <button className="back-btn" onClick={() => navigate('/subcontractors')}>&larr; Back</button>
        <h1>{isNew ? 'Add New Subcontractor' : subcontractor.company_name}</h1>
        {!isNew && (
          <span className={`status-badge ${subcontractor.status}`}>
            {subcontractor.status}
          </span>
        )}
      </div>

      <div className="profile-tabs">
        <button 
          className={activeTab === 'details' ? 'active' : ''} 
          onClick={() => setActiveTab('details')}
        >
          Details
        </button>
        <button 
          className={activeTab === 'certifications' ? 'active' : ''} 
          onClick={() => setActiveTab('certifications')}
        >
          Certifications ({certifications.length})
        </button>
        <button 
          className={activeTab === 'violations' ? 'active' : ''} 
          onClick={() => setActiveTab('violations')}
        >
          Violations ({violations.length})
        </button>
      </div>

      {activeTab === 'details' && (
        <form className="profile-form" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="company_name">Company Name *</label>
              <input
                id="company_name"
                type="text"
                value={subcontractor.company_name}
                onChange={(e) => handleChange('company_name', e.target.value)}
                className="form-input"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="contact_first_name">Contact First Name</label>
              <input
                id="contact_first_name"
                type="text"
                value={subcontractor.contact_first_name || ''}
                onChange={(e) => handleChange('contact_first_name', e.target.value)}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="contact_last_name">Contact Last Name</label>
              <input
                id="contact_last_name"
                type="text"
                value={subcontractor.contact_last_name || ''}
                onChange={(e) => handleChange('contact_last_name', e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="email">Email *</label>
              <input
                id="email"
                type="email"
                value={subcontractor.email}
                onChange={(e) => handleChange('email', e.target.value)}
                className="form-input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="phone">Phone</label>
              <input
                id="phone"
                type="tel"
                value={subcontractor.phone || ''}
                onChange={(e) => handleChange('phone', e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="address_line1">Address</label>
            <input
              id="address_line1"
              type="text"
              value={subcontractor.address_line1 || ''}
              onChange={(e) => handleChange('address_line1', e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="city">City</label>
              <input
                id="city"
                type="text"
                value={subcontractor.city || ''}
                onChange={(e) => handleChange('city', e.target.value)}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="state">State</label>
              <input
                id="state"
                type="text"
                value={subcontractor.state || ''}
                onChange={(e) => handleChange('state', e.target.value)}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="zip_code">ZIP Code</label>
              <input
                id="zip_code"
                type="text"
                value={subcontractor.zip_code || ''}
                onChange={(e) => handleChange('zip_code', e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="ein">EIN</label>
              <input
                id="ein"
                type="text"
                value={subcontractor.ein || ''}
                onChange={(e) => handleChange('ein', e.target.value)}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="license_number">License Number</label>
              <input
                id="license_number"
                type="text"
                value={subcontractor.license_number || ''}
                onChange={(e) => handleChange('license_number', e.target.value)}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="license_state">License State</label>
              <input
                id="license_state"
                type="text"
                value={subcontractor.license_state || ''}
                onChange={(e) => handleChange('license_state', e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          {!isNew && (
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="status">Status</label>
                <select
                  id="status"
                  value={subcontractor.status}
                  onChange={(e) => handleChange('status', e.target.value)}
                  className="form-input"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="suspended">Suspended</option>
                  <option value="blacklisted">Blacklisted</option>
                </select>
              </div>
            </div>
          )}

          {error && <div className="form-error">{error}</div>}
          {saveSuccess && <div className="form-success">
            {isNew ? 'Subcontractor created successfully!' : 'Profile saved successfully!'}
          </div>}

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : (isNew ? 'Create Subcontractor' : 'Save Profile')}
            </button>
            <button type="button" className="btn-secondary" onClick={handleCancel}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {activeTab === 'certifications' && !isNew && (
        <div className="certifications-section">
          <div className="section-header">
            <h2>Certifications</h2>
          </div>
          
          <DocumentUpload 
            subcontractorId={subcontractor.id} 
            onUploadComplete={() => {
              certificationApi.getAll().then(certs => certs.filter(c => c.subcontractor_id === subcontractor.id)).then(setCertifications);
            }}
          />
          
          {certifications.length === 0 ? (
            <div className="empty-state">No certifications on file</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Number</th>
                  <th>Issue Date</th>
                  <th>Expiration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {certifications.map(cert => (
                  <tr key={cert.id}>
                    <td>{cert.certification_type}</td>
                    <td>{cert.certification_number || 'N/A'}</td>
                    <td>{formatDate(cert.issue_date)}</td>
                    <td>{formatDate(cert.expiration_date)}</td>
                    <td>
                      <span className={`status-badge ${getStatusBadgeClass(cert.status)}`}>
                        {cert.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'certifications' && isNew && (
        <div className="empty-state">
          <p>Save the subcontractor first to upload certifications.</p>
        </div>
      )}

      {activeTab === 'violations' && (
        <div className="violations-section">
          {violations.length === 0 ? (
            <div className="empty-state">No violations on record</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Issued Date</th>
                  <th>Description</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {violations.map(v => (
                  <tr key={v.id}>
                    <td>{v.violation_type}</td>
                    <td>{formatDate(v.issued_date)}</td>
                    <td>{v.description}</td>
                    <td>
                      <span className={`status-badge ${getStatusBadgeClass(v.status)}`}>
                        {v.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

export default SubcontractorProfile;