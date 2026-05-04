import React, { useState } from 'react';

const CredentialUpload = () => {
  const [documentType, setDocumentType] = useState('Insurance Certificate');
  const [isUploading, setIsUploading] = useState(false);

  const handleFileUpload = (e) => {
    setIsUploading(true);
    // Simulate file upload process
    setTimeout(() => {
      setIsUploading(false);
    }, 2000);
  };

  return (
    <div className="credential-upload">
      <h2>Credential Upload Portal</h2>
      <div className="upload-form">
        <div>
          <label htmlFor="fileUpload">Upload Certification Documents:</label>
          <input id="fileUpload" type="file" multiple onChange={handleFileUpload} />
        </div>
        <div>
          <label htmlFor="documentType">Document Type:</label>
          <select id="documentType" value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
            <option>Insurance Certificate</option>
            <option>License</option>
            <option>OSHA Training Certificate</option>
          </select>
        </div>
        <button 
          onClick={() => alert('Documents submitted successfully!')}
          disabled={isUploading}
        >
          {isUploading ? 'Uploading...' : 'Submit Documents'}
        </button>
      </div>
    </div>
  );
};

export default CredentialUpload;