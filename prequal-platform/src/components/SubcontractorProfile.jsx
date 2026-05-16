import React, { useState, useEffect } from 'react';
import { contractorApi, complianceApi } from '../api/client';
import './SubcontractorProfile.css';

const SubcontractorProfile = () => {
  const [profile, setProfile] = useState({
    companyName: '',
    dbaName: '',
    companyAddress: '',
    contactName: '',
    contactTitle: '',
    contactEmail: '',
    contactPhone: '',
    website: ''
  });

  const [compliance, setCompliance] = useState({
    status: 'UNKNOWN',
    score: 0,
    lastUpdated: ''
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [certifications, setCertifications] = useState([]);
  const [violations, setViolations] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [contractors, status, certs, viols] = await Promise.all([
          contractorApi.getAll(),
          complianceApi.getStatus(),
          contractorApi.getCertifications('1'),
          contractorApi.getViolations('1')
        ]);

        if (contractors.length > 0) {
          const contractor = contractors[0];
          setProfile({
            companyName: contractor.company_name,
            dbaName: '',
            companyAddress: contractor.address,
            contactName: contractor.contact_name,
            contactTitle: '',
            contactEmail: contractor.email,
            contactPhone: contractor.phone,
            website: ''
          });
        }

        setCompliance({
          status: status.overall_status,
          score: status.compliance_score,
          lastUpdated: status.last_updated
        });

        setCertifications(certs);
        setViolations(viols);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSave = () => {
    alert('Changes saved successfully!');
  };

  const handleCancel = () => {
    setProfile({
      companyName: '',
      dbaName: '',
      companyAddress: '',
      contactName: '',
      contactTitle: '',
      contactEmail: '',
      contactPhone: '',
      website: ''
    });
  };

  const handleViewDocuments = () => {
    alert('Navigating to document management...');
  };

  const handleEdit = () => {
    alert('Entering edit mode...');
  };

  const handleHistory = () => {
    alert('Showing history...');
  };

  const handleExport = () => {
    alert('Exporting data...');
  };

  if (loading) return <div className="subcontractor-profile">Loading profile...</div>;
  if (error) return <div className="subcontractor-profile error">{error}</div>;

  return (
    <div className="subcontractor-profile">
      <div className="header-section">
        <div className="logo">[COMPANY LOGO]</div>
        <div className="user-info">User: {profile.contactName || 'Admin'}</div>
        <div className="action-buttons">
          <button onClick={handleEdit}>EDIT</button>
          <button onClick={handleHistory}>HISTORY</button>
          <button onClick={handleExport}>EXPORT</button>
        </div>
      </div>
      
      <h1>SUBCONTRACTOR COMPLIANCE PROFILE</h1>
      
      <div className="profile-section">
        <h2>COMPANY INFORMATION</h2>
        <div className="section-content">
          <div className="input-group">
            <label htmlFor="companyName">Company Name:</label>
            <input 
              type="text" 
              id="companyName"
              name="companyName"
              value={profile.companyName}
              onChange={handleInputChange}
              placeholder="ABC Construction Co." 
            />
          </div>
          <div className="input-group">
            <label htmlFor="dbaName">DBA Name:</label>
            <input 
              type="text" 
              id="dbaName"
              name="dbaName"
              value={profile.dbaName}
              onChange={handleInputChange}
              placeholder="ABC Co." 
            />
          </div>
          <div className="input-group">
            <label htmlFor="companyAddress">Company Address:</label>
            <textarea 
              id="companyAddress"
              name="companyAddress"
              value={profile.companyAddress}
              onChange={handleInputChange}
              placeholder={"123 Main Street\nAnytown, ST 12345"}
            ></textarea>
          </div>
          <div className="input-group">
            <label htmlFor="contactPhone">Phone Number:</label>
            <input 
              type="tel" 
              id="contactPhone"
              name="contactPhone"
              value={profile.contactPhone}
              onChange={handleInputChange}
              placeholder="(555) 123-4567"
            />
          </div>
          <div className="input-group">
            <label htmlFor="website">Website:</label>
            <input 
              type="url" 
              id="website"
              name="website"
              value={profile.website}
              onChange={handleInputChange}
              placeholder="www.abccompany.com"
            />
          </div>
        </div>
      </div>
      
      <div className="profile-section">
        <h2>PRIMARY CONTACT</h2>
        <div className="section-content">
          <div className="input-group">
            <label htmlFor="contactName">Contact Name:</label>
            <input 
              type="text" 
              id="contactName"
              name="contactName"
              value={profile.contactName}
              onChange={handleInputChange}
              placeholder="John Smith" 
            />
          </div>
          <div className="input-group">
            <label htmlFor="contactTitle">Contact Title:</label>
            <input 
              type="text" 
              id="contactTitle"
              name="contactTitle"
              value={profile.contactTitle}
              onChange={handleInputChange}
              placeholder="Project Manager" 
            />
          </div>
          <div className="input-group">
            <label htmlFor="contactEmail">Contact Email:</label>
            <input 
              type="email" 
              id="contactEmail"
              name="contactEmail"
              value={profile.contactEmail}
              onChange={handleInputChange}
              placeholder="jsmith@abccompany.com" 
            />
          </div>
          <div className="input-group">
            <label htmlFor="contactPhone2">Contact Phone:</label>
            <input 
              type="tel" 
              id="contactPhone2"
              name="contactPhone"
              value={profile.contactPhone}
              onChange={handleInputChange}
              placeholder="(555) 987-6543"
            />
          </div>
        </div>
      </div>
      
      <div className="profile-section">
        <h2>COMPLIANCE STATUS</h2>
        <div className="section-content">
          <div className="input-group">
            <label htmlFor="overallStatus">Overall Status:</label>
            <span id="overallStatus" className="compliance-value">{compliance.status}</span>
          </div>
          <div className="input-group">
            <label htmlFor="complianceScore">Compliance Score:</label>
            <div className="compliance-score">
              <span className="score-text">{compliance.score}%</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{width: `${compliance.score}%`}}></div>
              </div>
              <span className="score-text">{compliance.score}/100</span>
            </div>
          </div>
          <div className="input-group">
            <label htmlFor="lastUpdated">Last Updated:</label>
            <span id="lastUpdated" className="compliance-value">{compliance.lastUpdated}</span>
          </div>
        </div>
      </div>

      <div className="profile-section">
        <h2>CERTIFICATIONS ({certifications.length})</h2>
        <div className="section-content">
          {certifications.length === 0 ? (
            <p>No certifications on file.</p>
          ) : (
            <ul className="cert-list">
              {certifications.map(cert => (
                <li key={cert.id} className={`cert-item ${cert.status}`}>
                  {cert.certification_type} - Expires: {cert.expiry_date}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="profile-section">
        <h2>VIOLATIONS ({violations.length})</h2>
        <div className="section-content">
          {violations.length === 0 ? (
            <p>No violations on record.</p>
          ) : (
            <ul className="violation-list">
              {violations.map(viol => (
                <li key={viol.id} className={`violation-item ${viol.status}`}>
                  {viol.violation_type}: {viol.description} ({viol.date}) - {viol.status}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      
      <div className="action-buttons">
        <button onClick={handleSave}>SAVE CHANGES</button>
        <button onClick={handleCancel}>CANCEL</button>
        <button onClick={handleViewDocuments}>VIEW DOCUMENTS</button>
      </div>
    </div>
  );
};

export default SubcontractorProfile;