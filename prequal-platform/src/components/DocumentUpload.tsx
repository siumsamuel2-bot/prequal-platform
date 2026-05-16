import { useState, useRef } from 'react';
import { credentialsApi } from '../api/client';

interface DocumentUploadProps {
  subcontractorId: string;
  onUploadComplete?: () => void;
}

const DocumentUpload = ({ subcontractorId, onUploadComplete }: DocumentUploadProps) => {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [certificationType, setCertificationType] = useState('OSHA 30');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const certificationTypes = [
    'OSHA 30',
    'OSHA 10',
    'First Aid/CPR',
    'Commercial License',
    'Insurance Certificate',
    'W-9 Form',
    'Safety Program',
    'Drug Test',
    'Background Check',
    'Other'
  ];

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleUpload(file);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUpload(file);
    }
  };

  const handleUpload = async (file: File) => {
    setError(null);
    setSuccess(null);
    
    const validTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/jpg',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    
    if (!validTypes.includes(file.type)) {
      setError('Invalid file type. Please upload PDF, JPEG, PNG, or Word document.');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('File too large. Maximum size is 10MB.');
      return;
    }

    setUploading(true);

    try {
      await credentialsApi.upload(subcontractorId, file, certificationType);
      setSuccess('Document uploaded successfully! It will be processed shortly.');
      onUploadComplete?.();
      
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  return (
    <div className="document-upload">
      <h3>Upload Credential Document</h3>
      
      <div className="upload-form">
        <div className="form-group">
          <label htmlFor="cert-type">Certification Type</label>
          <select
            id="cert-type"
            value={certificationType}
            onChange={(e) => setCertificationType(e.target.value)}
            className="form-input"
          >
            {certificationTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        <div
          className={`drop-zone ${dragOver ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          
          {uploading ? (
            <div className="upload-progress">
              <div className="spinner"></div>
              <p>Uploading...</p>
            </div>
          ) : (
            <>
              <div className="upload-icon">📄</div>
              <p className="upload-text">
                Drag and drop a file here, or <span className="browse-link">browse</span>
              </p>
              <p className="upload-hint">PDF, JPEG, PNG, or Word documents up to 10MB</p>
            </>
          )}
        </div>

        {error && <div className="upload-error">{error}</div>}
        {success && <div className="upload-success">{success}</div>}
      </div>
    </div>
  );
};

export default DocumentUpload;