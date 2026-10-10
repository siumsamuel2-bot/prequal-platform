import { useState, useEffect, useMemo } from 'react';
import { complianceApi, violationApi, certificationApi, projectApi, complianceAnalyticsApi, ComplianceStatus, Violation, Certification, Project, SubcontractorWithDetails, ComplianceTrendPoint, ComplianceSummaryData, StateCredentialRecord, StateCredentialSummary } from '../api/client';
import { Loading, EmptyState } from './Loading';
import { NoAccessState, isForbiddenError } from './NoAccessState';
import { isAdmin } from '../utils/auth';
import FeedbackWidget from './FeedbackWidget';
import { useToast } from './ToastContext';
import { QuickAddSubcontractorModal } from './QuickAddSubcontractorModal';
import { useAnalytics } from '../hooks/useAnalytics';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './ComplianceDashboard.css';

interface ExpandedRow {
  subcontractorId: string;
  violations: Violation[];
  certifications: Certification[];
  stateCredentials: StateCredentialRecord[];
}

type DashboardTab = 'table' | 'state' | 'analytics';

const ComplianceDashboard = () => {
  const toast = useToast();
  const { trackExport } = useAnalytics();
  const [complianceData, setComplianceData] = useState<ComplianceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'compliant' | 'non_compliant'>('all');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [expandedDetails, setExpandedDetails] = useState<Record<string, ExpandedRow>>({});
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [activeTab, setActiveTab] = useState<DashboardTab>('table');
  const [trendData, setTrendData] = useState<ComplianceTrendPoint[]>([]);
  const [summaryData, setSummaryData] = useState<ComplianceSummaryData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [stateCredSummary, setStateCredSummary] = useState<StateCredentialSummary | null>(null);
  const [complianceDenied, setComplianceDenied] = useState(false);

  const isAdminUser = isAdmin();

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await projectApi.getAll();
        setProjects(data);
      } catch (err) {
        console.error('Failed to load projects', err);
      }
    };
    fetchProjects();
  }, []);

  useEffect(() => {
    const fetchComplianceData = async () => {
      setLoading(true);
      try {
        const data = await complianceApi.getStatus(selectedProject || undefined);
        setComplianceData(data);
        setComplianceDenied(false);
      } catch (err) {
        if (isForbiddenError(err) && !isAdminUser) {
          // Fail-closed 403 for this account (no resolvable team): show the calm
          // no-access state instead of an error toast (MID-657).
          setComplianceData([]);
          setComplianceDenied(true);
        } else {
          setComplianceDenied(false);
          toast.error(err instanceof Error ? err.message : 'Failed to load compliance data');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchComplianceData();
  }, [selectedProject, toast, isAdminUser]);

  useEffect(() => {
    const fetchAnalyticsData = async () => {
      if (activeTab !== 'analytics') return;
      setAnalyticsLoading(true);
      try {
        const [trends, summary] = await Promise.all([
          complianceAnalyticsApi.getTrends(30),
          complianceAnalyticsApi.getSummary()
        ]);
        setTrendData(trends);
        setSummaryData(summary);
      } catch (err) {
        console.error('Failed to load analytics data', err);
      } finally {
        setAnalyticsLoading(false);
      }
    };
    fetchAnalyticsData();
  }, [activeTab]);

  useEffect(() => {
    const fetchStateCredSummary = async () => {
      try {
        const summary = await complianceApi.getStateCredentialsSummary();
        setStateCredSummary(summary);
      } catch (err) {
        if (!isForbiddenError(err)) {
          console.error('Failed to load state credential summary', err);
        }
        setStateCredSummary(null);
      }
    };
    fetchStateCredSummary();
  }, []);

  const filteredData = useMemo(() => {
    return complianceData.filter(item => {
      const matchesSearch = item.company_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' ||
        (statusFilter === 'compliant' && item.status === 'COMPLIANT') ||
        (statusFilter === 'non_compliant' && item.status === 'NON_COMPLIANT');
      return matchesSearch && matchesStatus;
    });
  }, [complianceData, searchTerm, statusFilter]);

  const stateLevelData = useMemo(() => {
    const stateMap: Record<string, { state: string; total: number; compliant: number; nonCompliant: number; avgScore: number }> = {};
    complianceData.forEach(item => {
      const state = item.state || 'Unknown';
      if (!stateMap[state]) {
        stateMap[state] = { state, total: 0, compliant: 0, nonCompliant: 0, avgScore: 0 };
      }
      stateMap[state].total++;
      if (item.status === 'COMPLIANT') {
        stateMap[state].compliant++;
      } else {
        stateMap[state].nonCompliant++;
      }
      stateMap[state].avgScore += item.compliance_score;
    });
    return Object.values(stateMap).map(s => ({
      ...s,
      avgScore: s.total > 0 ? s.avgScore / s.total : 0,
      complianceRate: s.total > 0 ? (s.compliant / s.total) * 100 : 0
    })).sort((a, b) => b.total - a.total);
  }, [complianceData]);

  const scoreDistribution = useMemo(() => {
    const buckets = [
      { range: '0-20', count: 0 },
      { range: '21-40', count: 0 },
      { range: '41-60', count: 0 },
      { range: '61-80', count: 0 },
      { range: '81-100', count: 0 }
    ];
    complianceData.forEach(item => {
      const score = item.compliance_score;
      if (score <= 20) buckets[0].count++;
      else if (score <= 40) buckets[1].count++;
      else if (score <= 60) buckets[2].count++;
      else if (score <= 80) buckets[3].count++;
      else buckets[4].count++;
    });
    return buckets;
  }, [complianceData]);

  const toggleRow = async (subcontractorId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(subcontractorId)) {
      newExpanded.delete(subcontractorId);
    } else {
      newExpanded.add(subcontractorId);
      if (!expandedDetails[subcontractorId]) {
        try {
          const [violationsData, certsData, stateCredsData] = await Promise.all([
            violationApi.getAll().then(v => v.filter(vi => vi.subcontractor_id === subcontractorId)),
            certificationApi.getAll().then(c => c.filter(cert => cert.subcontractor_id === subcontractorId)),
            complianceApi.getStateCredentials({ subcontractor_id: subcontractorId }).catch(() => [])
          ]);
          setExpandedDetails(prev => ({
            ...prev,
            [subcontractorId]: { subcontractorId, violations: violationsData, certifications: certsData, stateCredentials: stateCredsData }
          }));
        } catch (err) {
          toast.error('Failed to load details');
        }
      }
    }
    setExpandedRows(newExpanded);
  };

  const handleExportCSV = async () => {
    trackExport('compliance', 'csv');
    try {
      const response = await fetch('/api/compliance/export?format=csv', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance-dashboard-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('CSV report downloaded successfully');
    } catch (err) {
      toast.error('Failed to export CSV');
    }
  };

  const handleExportPDF = async () => {
    trackExport('compliance', 'pdf');
    try {
      const response = await fetch('/api/compliance/dashboard/pdf', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });
      if (!response.ok) throw new Error('PDF export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance-dashboard-${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('PDF report downloaded successfully');
    } catch (err) {
      toast.error('Failed to export PDF');
    }
  };

  const handleQuickAddSuccess = async (newSubcontractor: SubcontractorWithDetails) => {
    toast.success(`${newSubcontractor.company_name} added to project with compliance score: ${newSubcontractor.compliance_score?.toFixed(0) || 'N/A'}`);
    const data = await complianceApi.getStatus(selectedProject || undefined);
    setComplianceData(data);
  };

  const handleQuickAdd = () => {
    if (!selectedProject) {
      toast.error('Please select a project first');
      return;
    }
    setShowQuickAdd(true);
  };

  const getDaysUntil = (dateStr: string) => {
    const expDate = new Date(dateStr);
    const today = new Date();
    const diff = Math.ceil((expDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  };

  const getCertWarningLevel = (expirationDate: string) => {
    const days = getDaysUntil(expirationDate);
    if (days < 0) return 'expired';
    if (days <= 30) return 'critical';
    if (days <= 60) return 'warning';
    return 'valid';
  };

  const formatDate = (dateStr: string | undefined | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  };

  if (loading) {
    return <div className="compliance-dashboard"><Loading message="Loading compliance data..." fullScreen /></div>;
  }

  if (complianceDenied && !isAdminUser) {
    return (
      <div className="compliance-dashboard">
        <div className="compliance-header">
          <div className="header-left">
            <h1>Compliance Dashboard</h1>
            <p className="header-subtitle">Violation history and certification status for all subcontractors</p>
          </div>
        </div>
        <NoAccessState variant="no-access" />
      </div>
    );
  }

  return (
    <div className="compliance-dashboard">
      <div className="compliance-header">
        <div className="header-left">
          <h1>Compliance Dashboard</h1>
          <p className="header-subtitle">Violation history and certification status for all subcontractors</p>
        </div>
        <div className="header-actions">
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="project-select"
          >
            <option value="">All Projects</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.project_name}</option>
            ))}
          </select>
          <button className="export-btn secondary" onClick={handleQuickAdd}>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Quick Add
          </button>
          <button className="export-btn secondary" onClick={handleExportCSV}>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </button>
          <button className="export-btn primary" onClick={handleExportPDF}>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export PDF
          </button>
          <a className="export-btn secondary" href="/support">
            💬 Support
          </a>
        </div>
      </div>

      <div className="compliance-tabs">
        <button
          className={`tab-btn ${activeTab === 'table' ? 'active' : ''}`}
          onClick={() => setActiveTab('table')}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Compliance Table
        </button>
        <button
          className={`tab-btn ${activeTab === 'state' ? 'active' : ''}`}
          onClick={() => setActiveTab('state')}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          State Level
        </button>
        {isAdminUser && (
        <button
          className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Analytics
        </button>
        )}
      </div>

      {activeTab === 'table' && (
      <>
      <div className="compliance-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by company name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        <div className="filter-group">
          <label>Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'compliant' | 'non_compliant')}
            className="filter-select"
          >
            <option value="all">All</option>
            <option value="compliant">Compliant</option>
            <option value="non_compliant">Non-Compliant</option>
          </select>
        </div>
        <div className="compliance-summary">
          <span className="summary-item">
            <span className="summary-dot compliant"></span>
            {complianceData.filter(d => d.status === 'COMPLIANT').length} Compliant
          </span>
          <span className="summary-item">
            <span className="summary-dot non-compliant"></span>
            {complianceData.filter(d => d.status === 'NON_COMPLIANT').length} Non-Compliant
          </span>
          {stateCredSummary && (
            <>
              <span className="summary-item">
                <span className="summary-dot" style={{ backgroundColor: '#3b82f6' }}></span>
                {stateCredSummary.active} State Verified
              </span>
              <span className="summary-item">
                <span className="summary-dot" style={{ backgroundColor: '#f59e0b' }}></span>
                {stateCredSummary.expiring_soon} Expiring Soon
              </span>
            </>
          )}
        </div>
      </div>

      {filteredData.length === 0 ? (
        complianceData.length === 0 && !searchTerm && statusFilter === 'all' && !isAdminUser ? (
          <NoAccessState variant="no-data" />
        ) : (
          <EmptyState
            title="No subcontractors match your filters"
            description="Try adjusting your search or filter criteria."
            icon={
              <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            }
          />
        )
      ) : (
        <div className="compliance-table-wrapper">
          <table className="compliance-table">
            <thead>
              <tr>
                <th className="expand-col"></th>
                <th>Company</th>
                <th>Compliance Score</th>
                <th>Status</th>
                <th>Active Certs</th>
                <th>Expiring (30d)</th>
                <th>Expired</th>
                <th>Open Violations</th>
                <th>Resolved</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map(item => (
                <>
                  <tr key={item.subcontractor_id} className={`main-row ${item.status === 'NON_COMPLIANT' ? 'non-compliant-row' : ''}`}>
                    <td className="expand-col">
                      <button
                        className={`expand-btn ${expandedRows.has(item.subcontractor_id) ? 'expanded' : ''}`}
                        onClick={() => toggleRow(item.subcontractor_id)}
                      >
                        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </td>
                    <td className="company-cell">
                      <a href={`/subcontractors/${item.subcontractor_id}`} className="company-link">
                        {item.company_name}
                      </a>
                    </td>
                    <td>
                      <div className={`score-badge ${item.compliance_score >= 70 ? 'good' : item.compliance_score >= 40 ? 'moderate' : 'poor'}`}>
                        {item.compliance_score.toFixed(0)}
                      </div>
                    </td>
                    <td>
                      <span className={`status-badge ${item.status === 'COMPLIANT' ? 'compliant' : 'non-compliant'}`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="number-cell">{item.active_certifications}</td>
                    <td className={`number-cell ${item.expiring_certifications > 0 ? 'warning' : ''}`}>
                      {item.expiring_certifications > 0 && '⚠️ '}{item.expiring_certifications}
                    </td>
                    <td className={`number-cell ${item.expired_certifications > 0 ? 'danger' : ''}`}>
                      {item.expired_certifications > 0 && '❌ '}{item.expired_certifications}
                    </td>
                    <td className={`number-cell ${item.open_violations > 0 ? 'danger' : ''}`}>
                      {item.open_violations > 0 && '⚠️ '}{item.open_violations}
                    </td>
                    <td className="number-cell">{item.resolved_violations}</td>
                  </tr>
                  {expandedRows.has(item.subcontractor_id) && (
                    <tr key={`${item.subcontractor_id}-expanded`} className="expanded-row">
                      <td colSpan={9}>
                        <div className="expanded-content">
                          {expandedDetails[item.subcontractor_id] ? (
                            <div className="details-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                              <div className="detail-section">
                                <h4>Violation History</h4>
                                {expandedDetails[item.subcontractor_id].violations.length === 0 ? (
                                  <p className="no-data">No violations on record</p>
                                ) : (
                                  <div className="violation-list">
                                    {expandedDetails[item.subcontractor_id].violations.map(v => (
                                      <div key={v.id} className={`violation-item ${v.status}`}>
                                        <div className="violation-header">
                                          <span className="violation-type">{v.violation_type}</span>
                                          <span className={`violation-status ${v.status}`}>{v.status}</span>
                                        </div>
                                        {v.description && <p className="violation-desc">{v.description}</p>}
                                        <div className="violation-meta">
                                          <span>Issued: {formatDate(v.issued_date)}</span>
                                          {v.resolved_date && <span>Resolved: {formatDate(v.resolved_date)}</span>}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                              <div className="detail-section">
                                <h4>Certification Status</h4>
                                {expandedDetails[item.subcontractor_id].certifications.length === 0 ? (
                                  <p className="no-data">No certifications on file</p>
                                ) : (
                                  <div className="cert-list">
                                    {expandedDetails[item.subcontractor_id].certifications.map(cert => {
                                      const warningLevel = getCertWarningLevel(cert.expiration_date);
                                      return (
                                        <div key={cert.id} className={`cert-item ${cert.status} ${warningLevel}`}>
                                          <div className="cert-header">
                                            <span className="cert-type">{cert.certification_type}</span>
                                            <span className={`cert-status ${cert.status} ${warningLevel}`}>
                                              {cert.status.toUpperCase()}
                                              {warningLevel === 'critical' && ' - EXPIRING SOON'}
                                              {warningLevel === 'expired' && ' - EXPIRED'}
                                            </span>
                                          </div>
                                          <div className="cert-meta">
                                            {cert.certification_number && <span>#{cert.certification_number}</span>}
                                            {cert.issuing_authority && <span>Issued by: {cert.issuing_authority}</span>}
                                          </div>
                                          <div className="cert-dates">
                                            {cert.issue_date && <span>Issued: {formatDate(cert.issue_date)}</span>}
                                            <span className={`expiration ${warningLevel}`}>
                                              Expires: {formatDate(cert.expiration_date)}
                                              {warningLevel !== 'valid' && ` (${getDaysUntil(cert.expiration_date)} days)`}
                                            </span>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                              <div className="detail-section">
                                <h4>State Credentials</h4>
                                {expandedDetails[item.subcontractor_id].stateCredentials.length === 0 ? (
                                  <p className="no-data">No state credentials found</p>
                                ) : (
                                  <div className="state-cred-list">
                                    {expandedDetails[item.subcontractor_id].stateCredentials.map(sc => (
                                      <div key={sc.id} className={`state-cred-item ${sc.status}`}>
                                        <div className="cert-header">
                                          <span className="cert-type">{sc.credential_type}</span>
                                          <span className={`cert-status ${sc.status}`}>{sc.status.toUpperCase()}</span>
                                        </div>
                                        <div className="cert-meta">
                                          <span>{sc.state_code} - #{sc.credential_number}</span>
                                        </div>
                                        <div className="cert-dates">
                                          {sc.issue_date && <span>Issued: {formatDate(sc.issue_date)}</span>}
                                          <span className={`expiration ${sc.expiration_date ? getCertWarningLevel(sc.expiration_date) : ''}`}>
                                            Expires: {formatDate(sc.expiration_date)}
                                          </span>
                                        </div>
                                        {sc.last_synced_at && (
                                          <div className="cert-meta">
                                            <span>Synced: {formatDate(sc.last_synced_at)}</span>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <Loading message="Loading details..." />
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="compliance-footer">
        <p>Showing {filteredData.length} of {complianceData.length} subcontractors</p>
      </div>
      </>
      )}

      {activeTab === 'state' && (
        <div className="state-level-view">
          <div className="state-header">
            <h2>Compliance by State</h2>
            <p>Subcontractor compliance breakdown by operating state</p>
          </div>
          <div className="state-table-wrapper">
            {stateLevelData.length === 0 ? (
              !isAdminUser ? (
                <NoAccessState variant="no-data" />
              ) : (
              <EmptyState
                title="No state data available"
                description="State information will appear once subcontractors have location data."
                icon={
                  <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                  </svg>
                }
              />
              )
            ) : (
              <table className="state-table">
                <thead>
                  <tr>
                    <th>State</th>
                    <th>Total Subcontractors</th>
                    <th>Compliant</th>
                    <th>Non-Compliant</th>
                    <th>Avg. Score</th>
                    <th>Compliance Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {stateLevelData.map(s => (
                    <tr key={s.state}>
                      <td className="state-cell">{s.state}</td>
                      <td className="number-cell">{s.total}</td>
                      <td className="number-cell compliant">{s.compliant}</td>
                      <td className="number-cell non-compliant">{s.nonCompliant}</td>
                      <td className="number-cell">
                        <span className={`score-badge ${s.avgScore >= 70 ? 'good' : s.avgScore >= 40 ? 'moderate' : 'poor'}`}>
                          {s.avgScore.toFixed(0)}
                        </span>
                      </td>
                      <td className="number-cell">
                        <div className="rate-bar">
                          <div className="rate-fill" style={{ width: `${s.complianceRate}%` }}></div>
                          <span>{s.complianceRate.toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {isAdminUser && activeTab === 'analytics' && (
        <div className="analytics-view">
          <div className="analytics-header">
            <h2>Compliance Analytics</h2>
            <p>Compliance trends and distribution for the last 30 days</p>
          </div>
          {analyticsLoading ? (
            <Loading message="Loading analytics..." fullScreen />
          ) : (
            <div className="analytics-grid">
              {summaryData && (
                <div className="analytics-summary-cards">
                  <div className="summary-card">
                    <h3>Total Subcontractors</h3>
                    <p className="card-value">{summaryData.total_subcontractors}</p>
                  </div>
                  <div className="summary-card">
                    <h3>Compliance Rate</h3>
                    <p className="card-value">{summaryData.compliance_rate.toFixed(1)}%</p>
                  </div>
                  <div className="summary-card">
                    <h3>Expiring Soon (30d)</h3>
                    <p className="card-value warning">{summaryData.expiring_soon_30d}</p>
                  </div>
                  <div className="summary-card">
                    <h3>Open Violations</h3>
                    <p className="card-value danger">{summaryData.open_violations}</p>
                  </div>
                </div>
              )}

              <div className="charts-row">
                <div className="chart-container">
                  <h3>Compliance Score Distribution</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={scoreDistribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="range" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3b82f6" name="Subcontractors" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="chart-container">
                  <h3>Compliance Trend (30 Days)</h3>
                  {trendData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={trendData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis domain={[0, 100]} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="compliance_percentage" stroke="#10b981" name="Compliance %" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="no-data">No trend data available</p>
                  )}
                </div>
              </div>

              {summaryData && (
                <div className="charts-row">
                  <div className="chart-container">
                    <h3>Certification Status</h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={[
                            { name: 'Valid', value: summaryData.valid_certifications, color: '#10b981' },
                            { name: 'Expired', value: summaryData.expired_certifications, color: '#ef4444' },
                            { name: 'Pending', value: summaryData.pending_verification_certs, color: '#f59e0b' }
                          ]}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          outerRadius={100}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {[
                            { name: 'Valid', value: summaryData.valid_certifications, color: '#10b981' },
                            { name: 'Expired', value: summaryData.expired_certifications, color: '#ef4444' },
                            { name: 'Pending', value: summaryData.pending_verification_certs, color: '#f59e0b' }
                          ].map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {showQuickAdd && (
        <QuickAddSubcontractorModal
          isOpen={showQuickAdd}
          projectId={selectedProject}
          projectName={projects.find(p => p.id === selectedProject)?.project_name || 'Unknown Project'}
          onClose={() => setShowQuickAdd(false)}
          onSuccess={handleQuickAddSuccess}
        />
      )}
      <FeedbackWidget surface="compliance_dashboard" />
    </div>
  );
};

export default ComplianceDashboard;