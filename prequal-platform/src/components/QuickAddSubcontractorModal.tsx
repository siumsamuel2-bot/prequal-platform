import { useState, useEffect, useRef } from 'react';
import { projectApi, SubcontractorWithDetails } from '../api/client';

interface QuickAddSubcontractorModalProps {
  isOpen: boolean;
  projectId: string;
  projectName: string;
  onClose: () => void;
  onSuccess: (subcontractor: SubcontractorWithDetails) => void;
}

interface FormData {
  company_name: string;
  contact_first_name: string;
  contact_last_name: string;
  email: string;
  phone: string;
  address_line1: string;
  city: string;
  state: string;
  zip_code: string;
  ein: string;
  license_number: string;
  license_state: string;
}

const initialFormData: FormData = {
  company_name: '',
  contact_first_name: '',
  contact_last_name: '',
  email: '',
  phone: '',
  address_line1: '',
  city: '',
  state: '',
  zip_code: '',
  ein: '',
  license_number: '',
  license_state: '',
};

export const QuickAddSubcontractorModal: React.FC<QuickAddSubcontractorModalProps> = ({
  isOpen,
  projectId,
  projectName,
  onClose,
  onSuccess,
}) => {
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      firstInputRef.current?.focus();
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const submitData: Record<string, string> = { ...formData };
      Object.keys(submitData).forEach(key => {
        if (!submitData[key]) delete submitData[key];
      });

      const result = await projectApi.quickAddSubcontractor(projectId, submitData as any);
      setFormData(initialFormData);
      onSuccess(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add subcontractor');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="quick-add-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .quick-add-modal-overlay {
          position: fixed;
          inset: 0;
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: rgba(0, 0, 0, 0.5);
          animation: fadeIn 0.2s ease-out;
        }
        .quick-add-modal {
          background-color: white;
          border-radius: 12px;
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
          max-width: 560px;
          width: 90%;
          max-height: 90vh;
          overflow-y: auto;
          animation: slideUp 0.2s ease-out;
        }
        .quick-add-modal-header {
          padding: 20px 24px;
          border-bottom: 1px solid #e5e7eb;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .quick-add-modal-header h2 {
          font-size: 18px;
          font-weight: 600;
          color: #111827;
          margin: 0;
        }
        .quick-add-modal-header p {
          font-size: 13px;
          color: #6b7280;
          margin: 4px 0 0 0;
        }
        .close-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 4px;
          color: #6b7280;
          border-radius: 4px;
        }
        .close-btn:hover {
          background-color: #f3f4f6;
          color: #374151;
        }
        .quick-add-modal-body {
          padding: 24px;
        }
        .quick-add-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .form-group.full-width {
          grid-column: 1 / -1;
        }
        .form-group label {
          font-size: 13px;
          font-weight: 500;
          color: #374151;
        }
        .form-group label .required {
          color: #ef4444;
        }
        .form-group input, .form-group select {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .form-group input:focus, .form-group select:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .form-group input::placeholder {
          color: #9ca3af;
        }
        .form-section {
          font-size: 12px;
          font-weight: 600;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-top: 8px;
          padding-bottom: 8px;
          border-bottom: 1px solid #e5e7eb;
        }
        .quick-add-error {
          background-color: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 6px;
          padding: 12px;
          color: #991b1b;
          font-size: 14px;
        }
        .quick-add-modal-footer {
          padding: 16px 24px;
          border-top: 1px solid #e5e7eb;
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          background-color: #f9fafb;
          border-radius: 0 0 12px 12px;
        }
        .btn {
          padding: 10px 16px;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .btn-secondary {
          background-color: white;
          color: #374151;
          border: 1px solid #d1d5db;
        }
        .btn-secondary:hover:not(:disabled) {
          background-color: #f9fafb;
        }
        .btn-primary {
          background-color: #3b82f6;
          color: white;
          border: none;
        }
        .btn-primary:hover:not(:disabled) {
          background-color: #2563eb;
        }
        .btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
      <div className="quick-add-modal">
        <div className="quick-add-modal-header">
          <div>
            <h2>Quick Add Subcontractor</h2>
            <p>Adding to project: {projectName}</p>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="quick-add-modal-body">
          {error && <div className="quick-add-error">{error}</div>}
          <form className="quick-add-form" onSubmit={handleSubmit}>
            <div className="form-section">Company Information</div>
            <div className="form-group full-width">
              <label htmlFor="company_name">Company Name <span className="required">*</span></label>
              <input
                ref={firstInputRef}
                type="text"
                id="company_name"
                name="company_name"
                value={formData.company_name}
                onChange={handleChange}
                placeholder="ABC Construction Co."
                required
              />
            </div>
            <div className="form-section">Contact Details</div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="contact_first_name">First Name</label>
                <input
                  type="text"
                  id="contact_first_name"
                  name="contact_first_name"
                  value={formData.contact_first_name}
                  onChange={handleChange}
                  placeholder="John"
                />
              </div>
              <div className="form-group">
                <label htmlFor="contact_last_name">Last Name</label>
                <input
                  type="text"
                  id="contact_last_name"
                  name="contact_last_name"
                  value={formData.contact_last_name}
                  onChange={handleChange}
                  placeholder="Smith"
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="email">Email <span className="required">*</span></label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="john@abcconstruction.com"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="phone">Phone</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="(555) 123-4567"
                />
              </div>
            </div>
            <div className="form-group full-width">
              <label htmlFor="address_line1">Address</label>
              <input
                type="text"
                id="address_line1"
                name="address_line1"
                value={formData.address_line1}
                onChange={handleChange}
                placeholder="123 Main Street"
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="city">City</label>
                <input
                  type="text"
                  id="city"
                  name="city"
                  value={formData.city}
                  onChange={handleChange}
                  placeholder="New York"
                />
              </div>
              <div className="form-group">
                <label htmlFor="state">State</label>
                <input
                  type="text"
                  id="state"
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                  placeholder="NY"
                  maxLength={2}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="zip_code">ZIP Code</label>
                <input
                  type="text"
                  id="zip_code"
                  name="zip_code"
                  value={formData.zip_code}
                  onChange={handleChange}
                  placeholder="10001"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ein">EIN (for compliance check)</label>
                <input
                  type="text"
                  id="ein"
                  name="ein"
                  value={formData.ein}
                  onChange={handleChange}
                  placeholder="12-3456789"
                />
              </div>
            </div>
            <div className="form-section">License Information</div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="license_number">License Number</label>
                <input
                  type="text"
                  id="license_number"
                  name="license_number"
                  value={formData.license_number}
                  onChange={handleChange}
                  placeholder="123456"
                />
              </div>
              <div className="form-group">
                <label htmlFor="license_state">License State</label>
                <input
                  type="text"
                  id="license_state"
                  name="license_state"
                  value={formData.license_state}
                  onChange={handleChange}
                  placeholder="NY"
                  maxLength={2}
                />
              </div>
            </div>
          </form>
        </div>
        <div className="quick-add-modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? (
              <>
                <svg style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite', marginRight: '8px' }} fill="none" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" opacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" />
                </svg>
                Adding...
              </>
            ) : 'Add Subcontractor'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default QuickAddSubcontractorModal;