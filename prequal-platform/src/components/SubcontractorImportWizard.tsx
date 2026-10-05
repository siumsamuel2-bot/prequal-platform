import { useState, useRef, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { subcontractorApi } from '../api/client';
import './SubcontractorImportWizard.css';

interface ParsedRow {
  company_name: string;
  contact_first_name?: string;
  contact_last_name?: string;
  email: string;
  phone?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  license_number?: string;
  license_state?: string;
  ein?: string;
  errors: string[];
  selected: boolean;
}

const SAMPLE_CSV = `company_name,contact_first_name,contact_last_name,email,phone,address_line1,city,state,zip_code,license_number,license_state,ein
Acme Construction,John,Smith,john@acmeconst.com,555-0101,123 Main St,Chicago,IL,60601,ABC123,IL,12-3456789
BuildRight Inc,Sarah,Johnson,sarah@buildright.com,555-0102,456 Oak Ave,Chicago,IL,60602,BR456,IL,98-7654321
Metro Contractors,Mike,Williams,mike@metro.com,555-0103,789 Elm Blvd,Chicago,IL,60603,MC789,IL,45-6789012`;

const REQUIRED_FIELDS = ['company_name', 'email'];
const OPTIONAL_FIELDS = ['contact_first_name', 'contact_last_name', 'phone', 'address_line1', 'city', 'state', 'zip_code', 'license_number', 'license_state', 'ein'];

export const SubcontractorImportWizard = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(1);
  const [importMethod, setImportMethod] = useState<'csv' | 'manual' | null>(null);
  const [parsedData, setParsedData] = useState<ParsedRow[]>([]);
  const [manualEntry, setManualEntry] = useState({
    company_name: '',
    contact_first_name: '',
    contact_last_name: '',
    email: '',
    phone: '',
    address_line1: '',
    city: '',
    state: '',
    zip_code: '',
    license_number: '',
    license_state: '',
    ein: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [importResults, setImportResults] = useState<{ success: number; failed: number } | null>(null);

  const handleCSVUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      parseCSV(content);
    };
    reader.readAsText(file);
  };

  const parseCSV = (content: string) => {
    const lines = content.trim().split('\n');
    if (lines.length < 2) {
      setError('CSV must have a header row and at least one data row');
      return;
    }

    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/"/g, ''));
    const missingHeaders = REQUIRED_FIELDS.filter(f => !headers.includes(f));
    if (missingHeaders.length > 0) {
      setError(`Missing required columns: ${missingHeaders.join(', ')}`);
      return;
    }

    const rows: ParsedRow[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]);
      const row: ParsedRow = {
        company_name: '',
        email: '',
        errors: [],
        selected: true
      };

      headers.forEach((header, index) => {
        const value = values[index]?.trim().replace(/^"|"$/g, '') || '';
        if (REQUIRED_FIELDS.includes(header)) {
          if (!value) {
            row.errors.push(`Missing required field: ${header}`);
          }
          (row as any)[header] = value;
        } else if (OPTIONAL_FIELDS.includes(header)) {
          (row as any)[header] = value;
        }
      });

      if (!row.email || !isValidEmail(row.email)) {
        row.errors.push('Invalid email format');
      }

      rows.push(row);
    }

    setParsedData(rows);
    setStep(2);
    setError('');
  };

  const parseCSVLine = (line: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        result.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    result.push(current);
    return result;
  };

  const isValidEmail = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const downloadSampleCSV = () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'subcontractors_import_sample.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleRowSelection = (index: number) => {
    setParsedData(prev => prev.map((row, i) => 
      i === index ? { ...row, selected: !row.selected } : row
    ));
  };

  const selectAll = (selected: boolean) => {
    setParsedData(prev => prev.map(row => ({ ...row, selected })));
  };

  const handleImport = async () => {
    setIsLoading(true);
    setError('');
    let success = 0;
    let failed = 0;

    const rowsToImport = importMethod === 'csv' 
      ? parsedData.filter(r => r.selected && r.errors.length === 0)
      : [{ ...manualEntry, errors: [] as string[], selected: true }];

    for (const row of rowsToImport) {
      try {
        const { errors, selected, ...subcontractorData } = row as any;
        await subcontractorApi.create(subcontractorData);
        success++;
      } catch (err) {
        failed++;
        console.error('Failed to import:', row.company_name, err);
      }
    }

    setImportResults({ success, failed });
    setStep(3);
    setIsLoading(false);
  };

  const updateManualEntry = (field: string, value: string) => {
    setManualEntry(prev => ({ ...prev, [field]: value }));
  };

  const isManualEntryValid = () => {
    return manualEntry.company_name.trim() && manualEntry.email.trim() && isValidEmail(manualEntry.email);
  };

  return (
    <div className="import-wizard-container">
      <div className="import-wizard-card">
        <div className="import-wizard-progress">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>1</div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>2</div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>3</div>
        </div>

        {step === 1 && (
          <div className="step-content">
            <h1 className="import-wizard-title">Import Subcontractors</h1>
            <p className="import-wizard-subtitle">Add subcontractors to your organization</p>

            {error && <div className="import-error">{error}</div>}

            <div className="import-methods">
              <div 
                className={`import-method-card ${importMethod === 'csv' ? 'selected' : ''}`}
                onClick={() => setImportMethod('csv')}
              >
                <span className="method-icon">📄</span>
                <span className="method-title">CSV Upload</span>
                <span className="method-desc">Import multiple subcontractors from a CSV file</span>
              </div>

              <div 
                className={`import-method-card ${importMethod === 'manual' ? 'selected' : ''}`}
                onClick={() => setImportMethod('manual')}
              >
                <span className="method-icon">✏️</span>
                <span className="method-title">Manual Entry</span>
                <span className="method-desc">Add a single subcontractor manually</span>
              </div>
            </div>

            {importMethod === 'csv' && (
              <div className="csv-upload-section">
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".csv"
                  onChange={handleCSVUpload}
                  style={{ display: 'none' }}
                />
                <button 
                  className="import-button"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Choose CSV File
                </button>
                <button 
                  className="import-button secondary"
                  onClick={downloadSampleCSV}
                >
                  Download Sample CSV
                </button>
                <p className="csv-hint">
                  Required columns: company_name, email<br/>
                  Optional: contact_first_name, contact_last_name, phone, address, city, state, zip, license_number, license_state, ein
                </p>
              </div>
            )}

            {importMethod === 'manual' && (
              <div className="manual-entry-section">
                <div className="form-row">
                  <div className="form-group">
                    <label>Company Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.company_name}
                      onChange={(e) => updateManualEntry('company_name', e.target.value)}
                      placeholder="Acme Construction"
                    />
                  </div>
                </div>
                <div className="form-row two-col">
                  <div className="form-group">
                    <label>Contact First Name</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.contact_first_name}
                      onChange={(e) => updateManualEntry('contact_first_name', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Contact Last Name</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.contact_last_name}
                      onChange={(e) => updateManualEntry('contact_last_name', e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Email *</label>
                    <input
                      type="email"
                      className="form-input"
                      value={manualEntry.email}
                      onChange={(e) => updateManualEntry('email', e.target.value)}
                      placeholder="contact@company.com"
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Phone</label>
                    <input
                      type="tel"
                      className="form-input"
                      value={manualEntry.phone}
                      onChange={(e) => updateManualEntry('phone', e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Address</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.address_line1}
                      onChange={(e) => updateManualEntry('address_line1', e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row three-col">
                  <div className="form-group">
                    <label>City</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.city}
                      onChange={(e) => updateManualEntry('city', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>State</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.state}
                      onChange={(e) => updateManualEntry('state', e.target.value)}
                      maxLength={2}
                    />
                  </div>
                  <div className="form-group">
                    <label>ZIP</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.zip_code}
                      onChange={(e) => updateManualEntry('zip_code', e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row two-col">
                  <div className="form-group">
                    <label>License Number</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.license_number}
                      onChange={(e) => updateManualEntry('license_number', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>License State</label>
                    <input
                      type="text"
                      className="form-input"
                      value={manualEntry.license_state}
                      onChange={(e) => updateManualEntry('license_state', e.target.value)}
                      maxLength={2}
                    />
                  </div>
                </div>

                <button 
                  className="import-button"
                  onClick={() => setStep(2)}
                  disabled={!isManualEntryValid()}
                >
                  Continue
                </button>
              </div>
            )}

            {importMethod && (
              <div className="import-actions">
                <button className="import-button secondary" onClick={() => navigate('/subcontractors')}>
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {step === 2 && importMethod === 'csv' && (
          <div className="step-content">
            <h1 className="import-wizard-title">Review Import ({parsedData.length} records)</h1>
            <p className="import-wizard-subtitle">Select the subcontractors you want to import</p>

            <div className="review-toolbar">
              <button className="select-all-btn" onClick={() => selectAll(true)}>Select All</button>
              <button className="select-all-btn" onClick={() => selectAll(false)}>Deselect All</button>
              <span className="selected-count">
                {parsedData.filter(r => r.selected).length} selected
              </span>
            </div>

            <div className="review-table-container">
              <table className="review-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Company</th>
                    <th>Contact</th>
                    <th>Email</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {parsedData.map((row, index) => (
                    <tr key={index} className={row.errors.length > 0 ? 'has-error' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={row.selected}
                          onChange={() => toggleRowSelection(index)}
                          disabled={row.errors.length > 0}
                        />
                      </td>
                      <td>{row.company_name}</td>
                      <td>{row.contact_first_name} {row.contact_last_name}</td>
                      <td>{row.email}</td>
                      <td>
                        {row.errors.length > 0 ? (
                          <span className="error-badge" title={row.errors.join(', ')}>
                            Error
                          </span>
                        ) : (
                          <span className="ready-badge">Ready</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="import-actions">
              <button className="import-button secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <button 
                className="import-button"
                onClick={handleImport}
                disabled={isLoading || parsedData.filter(r => r.selected && r.errors.length === 0).length === 0}
              >
                {isLoading ? 'Importing...' : `Import ${parsedData.filter(r => r.selected && r.errors.length === 0).length} Subcontractors`}
              </button>
            </div>
          </div>
        )}

        {step === 2 && importMethod === 'manual' && (
          <div className="step-content">
            <h1 className="import-wizard-title">Review Entry</h1>
            <p className="import-wizard-subtitle">Confirm the subcontractor details</p>

            <div className="review-card">
              <div className="review-field">
                <span className="field-label">Company</span>
                <span className="field-value">{manualEntry.company_name}</span>
              </div>
              <div className="review-field">
                <span className="field-label">Contact</span>
                <span className="field-value">{manualEntry.contact_first_name} {manualEntry.contact_last_name}</span>
              </div>
              <div className="review-field">
                <span className="field-label">Email</span>
                <span className="field-value">{manualEntry.email}</span>
              </div>
              {manualEntry.phone && (
                <div className="review-field">
                  <span className="field-label">Phone</span>
                  <span className="field-value">{manualEntry.phone}</span>
                </div>
              )}
              {manualEntry.address_line1 && (
                <div className="review-field">
                  <span className="field-label">Address</span>
                  <span className="field-value">{manualEntry.address_line1}, {manualEntry.city}, {manualEntry.state} {manualEntry.zip_code}</span>
                </div>
              )}
            </div>

            <div className="import-actions">
              <button className="import-button secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <button 
                className="import-button"
                onClick={handleImport}
                disabled={isLoading}
              >
                {isLoading ? 'Adding...' : 'Add Subcontractor'}
              </button>
            </div>
          </div>
        )}

        {step === 3 && importResults && (
          <div className="step-content">
            <div className="results-icon">✓</div>
            <h1 className="import-wizard-title">Import Complete</h1>
            <p className="import-wizard-subtitle">
              Successfully imported {importResults.success} subcontractor{importResults.success !== 1 ? 's' : ''}
              {importResults.failed > 0 && `, ${importResults.failed} failed`}
            </p>

            <div className="import-actions">
              <button className="import-button secondary" onClick={() => navigate('/subcontractors')}>
                View Subcontractors
              </button>
              <button className="import-button" onClick={() => navigate('/dashboard')}>
                Go to Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SubcontractorImportWizard;