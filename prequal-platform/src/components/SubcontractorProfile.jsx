import React, { useState } from 'react';
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
    website: '',
    contactPhone: ''
  });

  const [compliance, setCompliance] = useState({
    status: 'COMPLIANT',
    score: 85,
    lastUpdated: '2026-04-25'
  });

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
    // Reset to initial state
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

  return (
    <div className="subcontractor-profile">
      <div className="header-section">
        <div className="logo">[COMPANY LOGO]</div>
        <div className="user-info">User: John Contractor</div>
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
      
      <div className="action-buttons">
        <button onClick={handleSave}>SAVE CHANGES</button>
        <button onClick={handleCancel}>CANCEL</button>
        <button onClick={handleViewDocuments}>VIEW DOCUMENTS</button>
      </div>
    </div>
  );
};

export default SubcontractorProfile;