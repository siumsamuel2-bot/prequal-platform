import React, { useState, useRef, useCallback } from 'react';

const ACCEPTED_FILE_TYPES = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/jpg': '.jpg',
  'application/pdf': '.pdf',
  'application/msword': '.doc',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
};

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_EXTENSIONS = Object.values(ACCEPTED_FILE_TYPES).join(',');

const CredentialUpload = ({ subcontractorId, onUploadComplete }) => {
  const [documentType, setDocumentType] = useState('Insurance Certificate');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const fileInputRef = useRef(null);

  const validateFiles = useCallback((fileList) => {
    const errors = [];
    const validFiles = [];

    Array.from(fileList).forEach(file => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      const isTypeValid = Object.values(ACCEPTED_FILE_TYPES).includes(ext);
      const isSizeValid = file.size <= MAX_FILE_SIZE;

      if (!isTypeValid) {
        errors.push(`"${file.name}": Invalid file type. Accepted: ${ALLOWED_EXTENSIONS}`);
      } else if (!isSizeValid) {
        errors.push(`"${file.name}": File too large. Maximum size: 10MB`);
      } else {
        validFiles.push({
          file,
          id: Math.random().toString(36).substr(2, 9),
          status: 'pending',
        });
      }
    });

    setValidationErrors(errors);
    return validFiles;
  }, []);

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      const validFiles = validateFiles(droppedFiles);
      setFiles(prev => [...prev, ...validFiles]);
    }
  };

  const handleFileSelect = (e) => {
    const selectedFiles = e.target.files;
    if (selectedFiles.length > 0) {
      const validFiles = validateFiles(selectedFiles);
      setFiles(prev => [...prev, ...validFiles]);
    }
  };

  const handleRemoveFile = (fileId) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
    setValidationErrors([]);
  };

  const handleClearAll = () => {
    setFiles([]);
    setValidationErrors([]);
    setUploadStatus(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const simulateUpload = async () => {
    setIsUploading(true);
    setUploadProgress(0);
    setUploadStatus(null);

    const totalFiles = files.length;
    let completedFiles = 0;

    for (const fileObj of files) {
      setFiles(prev =>
        prev.map(f =>
          f.id === fileObj.id ? { ...f, status: 'uploading' } : f
        )
      );

      for (let progress = 0; progress <= 100; progress += 20) {
        await new Promise(resolve => setTimeout(resolve, 100));
        setUploadProgress(Math.round(((completedFiles * 100 + progress) / totalFiles)));
      }

      setFiles(prev =>
        prev.map(f =>
          f.id === fileObj.id ? { ...f, status: 'success' } : f
        )
      );
      completedFiles++;
    }

    setUploadProgress(100);
    setUploadStatus('success');
    setIsUploading(false);

    setTimeout(() => {
      setFiles([]);
      setUploadStatus(null);
      if (onUploadComplete) onUploadComplete();
    }, 2000);
  };

  const handleSubmit = () => {
    if (files.length === 0) {
      setValidationErrors(['Please select at least one file to upload']);
      return;
    }
    simulateUpload();
  };

  const getFileIcon = (fileName) => {
    const ext = fileName.split('.').pop().toLowerCase();
    if (['png', 'jpg', 'jpeg'].includes(ext)) {
      return (
        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    }
    if (ext === 'pdf') {
      return (
        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      );
    }
    return (
      <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    );
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="credential-upload">
      <h2>Credential Upload Portal</h2>

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS}
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {files.length === 0 ? (
          <div className="drop-zone-content">
            <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="drop-zone-text">
              Drag and drop files here or <span className="browse-link">click to browse</span>
            </p>
            <p className="drop-zone-hint">
              Accepted file types: PNG, JPG, PDF, DOC, DOCX (Max 10MB)
            </p>
          </div>
        ) : (
          <div className="file-list">
            {files.map(fileObj => (
              <div key={fileObj.id} className={`file-item ${fileObj.status}`}>
                <div className="file-icon">{getFileIcon(fileObj.file.name)}</div>
                <div className="file-info">
                  <span className="file-name">{fileObj.file.name}</span>
                  <span className="file-size">{formatFileSize(fileObj.file.size)}</span>
                </div>
                <div className="file-status">
                  {fileObj.status === 'uploading' && (
                    <span className="status-uploading">Uploading...</span>
                  )}
                  {fileObj.status === 'success' && (
                    <span className="status-success">Uploaded</span>
                  )}
                  {(fileObj.status === 'pending' || !fileObj.status) && (
                    <button
                      className="remove-btn"
                      onClick={(e) => { e.stopPropagation(); handleRemoveFile(fileObj.id); }}
                    >
                      <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {validationErrors.length > 0 && (
        <div className="validation-errors">
          {validationErrors.map((error, idx) => (
            <p key={idx} className="error-message">{error}</p>
          ))}
        </div>
      )}

      <div className="upload-form">
        <div className="form-group">
          <label htmlFor="documentType">Document Type:</label>
          <select
            id="documentType"
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            disabled={isUploading}
          >
            <option value="Insurance Certificate">Insurance Certificate</option>
            <option value="License">License</option>
            <option value="OSHA Training Certificate">OSHA Training Certificate</option>
            <option value="O2S2H Training Certificate">O2S2H Training Certificate</option>
            <option value="Other Document Type">Other Document Type</option>
          </select>
        </div>

        {isUploading && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
            </div>
            <span className="progress-text">{uploadProgress}% Complete</span>
          </div>
        )}

        {uploadStatus === 'success' && (
          <div className="upload-success">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Documents uploaded successfully!</span>
          </div>
        )}

        <div className="form-actions">
          <button
            onClick={handleSubmit}
            disabled={isUploading || files.length === 0}
            className="submit-btn"
          >
            {isUploading ? 'Uploading...' : 'Submit Documents'}
          </button>
          {files.length > 0 && !isUploading && (
            <button onClick={handleClearAll} className="clear-btn">
              Clear All
            </button>
          )}
        </div>
      </div>

      <style>{`
        .credential-upload {
          padding: 20px;
        }

        .credential-upload h2 {
          color: #555;
          margin-bottom: 15px;
        }

        .drop-zone {
          border: 2px dashed #e5e7eb;
          border-radius: 8px;
          padding: 40px 20px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s ease;
          background-color: #f9fafb;
          min-height: 200px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .drop-zone:hover {
          border-color: #2563eb;
          background-color: #eff6ff;
        }

        .drop-zone.dragging {
          border-color: #2563eb;
          background-color: #eff6ff;
          transform: scale(1.01);
        }

        .drop-zone.has-files {
          padding: 20px;
          min-height: auto;
          align-items: stretch;
        }

        .drop-zone-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          color: #6b7280;
        }

        .drop-zone-content svg {
          color: #9ca3af;
        }

        .drop-zone-text {
          font-size: 16px;
          margin: 0;
        }

        .browse-link {
          color: #2563eb;
          font-weight: 500;
        }

        .drop-zone-hint {
          font-size: 12px;
          color: #9ca3af;
          margin: 0;
        }

        .file-list {
          width: 100%;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .file-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
        }

        .file-item.uploading {
          border-color: #2563eb;
          background-color: #eff6ff;
        }

        .file-item.success {
          border-color: #10b981;
          background-color: #ecfdf5;
        }

        .file-icon {
          color: #6b7280;
          flex-shrink: 0;
        }

        .file-info {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .file-name {
          font-weight: 500;
          color: #111827;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .file-size {
          font-size: 12px;
          color: #6b7280;
        }

        .file-status {
          flex-shrink: 0;
        }

        .status-uploading {
          color: #2563eb;
          font-size: 12px;
        }

        .status-success {
          color: #10b981;
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .remove-btn {
          background: none;
          border: none;
          padding: 4px;
          cursor: pointer;
          color: #6b7280;
          border-radius: 4px;
        }

        .remove-btn:hover {
          background-color: #fee2e2;
          color: #dc2626;
        }

        .validation-errors {
          margin-top: 12px;
          padding: 12px;
          background-color: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 6px;
        }

        .error-message {
          color: #dc2626;
          font-size: 14px;
          margin: 0 0 4px 0;
        }

        .error-message:last-child {
          margin-bottom: 0;
        }

        .upload-form {
          margin-top: 20px;
        }

        .upload-form .form-group {
          margin-bottom: 16px;
        }

        .upload-form label {
          display: block;
          font-weight: 500;
          margin-bottom: 6px;
          color: #374151;
        }

        .upload-form select {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
          background-color: white;
          cursor: pointer;
        }

        .upload-form select:focus {
          outline: none;
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        .upload-form select:disabled {
          background-color: #f3f4f6;
          cursor: not-allowed;
        }

        .upload-progress {
          margin-bottom: 16px;
        }

        .progress-bar {
          width: 100%;
          height: 8px;
          background-color: #e5e7eb;
          border-radius: 4px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background-color: #2563eb;
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .progress-text {
          display: block;
          margin-top: 6px;
          font-size: 12px;
          color: #6b7280;
          text-align: center;
        }

        .upload-success {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px;
          background-color: #ecfdf5;
          border: 1px solid #a7f3d0;
          border-radius: 6px;
          color: #059669;
          margin-bottom: 16px;
        }

        .form-actions {
          display: flex;
          gap: 12px;
        }

        .submit-btn {
          flex: 1;
          background-color: #2563eb;
          color: white;
          padding: 12px 24px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s ease;
        }

        .submit-btn:hover:not(:disabled) {
          background-color: #1d4ed8;
        }

        .submit-btn:disabled {
          background-color: #9ca3af;
          cursor: not-allowed;
        }

        .clear-btn {
          background-color: white;
          color: #6b7280;
          padding: 12px 24px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .clear-btn:hover {
          background-color: #f3f4f6;
          border-color: #9ca3af;
        }
      `}</style>
    </div>
  );
};

export default CredentialUpload;