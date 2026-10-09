const API_BASE_URL = (typeof process !== 'undefined' && process.env && process.env.VITE_API_URL) || '/api';

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options;

    let url = `${this.baseUrl}${endpoint}`;

    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const token = localStorage.getItem('access_token');

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    };

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(error.detail || `HTTP error ${response.status}`, response.status);
    }

    return response.json();
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  async patch<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  teams: Team[];
}

export interface Team {
  id: string;
  name: string;
  description?: string;
  role: string;
  joined_at?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at?: string;
}

export interface OnboardingStatus {
  has_organization: boolean;
  has_project: boolean;
  has_subcontractor: boolean;
  step: number;
}

export interface Project {
  id: string;
  project_name: string;
  project_number?: string;
  description?: string;
  client_name?: string;
  client_contact?: string;
  start_date?: string;
  estimated_end_date?: string;
  actual_end_date?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  status: string;
  budget?: number;
  created_at?: string;
  updated_at?: string;
}

export interface SubcontractorWithDetails extends Subcontractor {
  certifications: Certification[];
  violations: Violation[];
  active_projects_count: number;
  compliance_score?: number;
}

export const organizationApi = {
  create: (data: { name: string; slug?: string }) =>
    apiClient.post<Organization>('/auth/organizations', data),

  getMe: () => apiClient.get<Organization>('/auth/organizations/me'),

  update: (data: { name?: string; slug?: string }) =>
    apiClient.patch<Organization>('/auth/organizations/me', data),

  getOnboardingStatus: () => apiClient.get<OnboardingStatus>('/auth/onboarding/status'),
};

export const authApi = {
  login: (username: string, password: string) =>
    apiClient.post<{ access_token: string; token_type: string }>('/auth/login', {
      username,
      password,
    }),

  register: (data: { email: string; password: string; name: string }) =>
    apiClient.post<{ access_token: string; token_type: string }>('/auth/register', data),

  getMe: () => apiClient.get<User>('/auth/me'),

  refreshToken: (refresh_token: string) =>
    apiClient.post<{ access_token: string; token_type: string }>('/auth/refresh', { refresh_token }),

  getTeams: () => apiClient.get<Team[]>('/auth/teams'),

  requestPasswordReset: (email: string) =>
    apiClient.post<{ message: string }>('/auth/password-reset-request', { email }),

  confirmPasswordReset: (token: string, newPassword: string) =>
    apiClient.post<{ message: string }>('/auth/password-reset/confirm', { token, new_password: newPassword }),

  getMFAStatus: () => apiClient.get<{ mfa_enabled: boolean; mfa_method: string | null }>('/auth/mfa/status'),

  enableMFA: (password: string) =>
    apiClient.post<{ secret: string; otpauth_url: string }>('/auth/mfa/enable', { password }),

  verifyMFA: (token: string) =>
    apiClient.post<{ message: string; backup_codes?: string[] }>('/auth/mfa/verify', { token }),

  disableMFA: (password: string, mfa_token: string) =>
    apiClient.post<{ message: string }>('/auth/mfa/disable', { password, mfa_token }),

  validateMFA: (userId: string, mfaToken: string) =>
    apiClient.post<{ access_token: string; token_type: string }>(`/auth/mfa/validate?user_id=${encodeURIComponent(userId)}&mfa_token=${encodeURIComponent(mfaToken)}`),
};

export const subcontractorApi = {
  getAll: () => apiClient.get<Subcontractor[]>('/subcontractors'),

  getById: (id: string) => apiClient.get<Subcontractor>(`/subcontractors/${id}`),

  create: (data: Omit<Subcontractor, 'id'>) =>
    apiClient.post<Subcontractor>('/subcontractors', data),

  update: (id: string, data: Partial<Subcontractor>) =>
    apiClient.put<Subcontractor>(`/subcontractors/${id}`, data),

  delete: (id: string) => apiClient.delete<{ message: string }>(`/subcontractors/${id}`),

  downloadReport: async (id: string) => {
    const response = await fetch(`${API_BASE_URL}/subcontractors/${id}/report`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    });
    if (!response.ok) throw new Error('Failed to download report');
    return response.blob();
  }
};

export const complianceApi = {
  getStatus: (projectId?: string) => apiClient.get<ComplianceStatus[]>('/compliance/status', projectId ? { params: { project_id: projectId } } : undefined),

  getAlerts: () => apiClient.get<ComplianceAlert[]>('/compliance/alerts'),

  getStateCredentials: (params?: { subcontractor_id?: string; state_code?: string }) =>
    apiClient.get<StateCredentialRecord[]>('/compliance/state-credentials', params ? { params: params } : undefined),

  getStateCredentialsSummary: () => apiClient.get<StateCredentialSummary>('/compliance/state-credentials/summary'),
};

export interface StateCredentialRecord {
  id: number;
  state_code: string;
  credential_number: string;
  credential_type: string;
  issuing_state: string;
  holder_name?: string;
  holder_address?: string;
  holder_city?: string;
  holder_state?: string;
  holder_zip?: string;
  issue_date?: string;
  expiration_date?: string;
  status: string;
  external_source_id?: string;
  external_source_url?: string;
  last_synced_at?: string;
}

export interface StateCredentialSummary {
  total: number;
  active: number;
  expiring_soon: number;
  expired: number;
  unmatched: number;
}

export const projectApi = {
  getAll: () => apiClient.get<Project[]>('/projects'),

  getById: (id: string) => apiClient.get<Project>(`/projects/${id}`),

  getSubcontractors: (projectId: string) => apiClient.get<SubcontractorWithDetails[]>(`/projects/${projectId}/subcontractors`),

  quickAddSubcontractor: (projectId: string, data: Omit<Subcontractor, 'id'>) =>
    apiClient.post<SubcontractorWithDetails>(`/projects/${projectId}/subcontractors/quick-add`, data),
};

export const contractorApi = {
  getAll: () => apiClient.get<Contractor[]>('/contractors'),

  getById: (id: string) => apiClient.get<Contractor>(`/contractors/${id}`),

  create: (data: Omit<Contractor, 'id'>) =>
    apiClient.post<Contractor>('/contractors', data),

  getCertifications: (contractorId: string) =>
    apiClient.get<Certification[]>(`/contractors/${contractorId}/certifications`),

  getViolations: (contractorId: string) =>
    apiClient.get<Violation[]>(`/contractors/${contractorId}/violations`),
};

export const certificationApi = {
  getAll: () => apiClient.get<Certification[]>('/certifications'),

  getById: (id: string) => apiClient.get<Certification>(`/certifications/${id}`),
};

export const violationApi = {
  getAll: () => apiClient.get<Violation[]>('/violations'),

  getById: (id: string) => apiClient.get<Violation>(`/violations/${id}`),
};

export interface Subcontractor {
  id: string;
  company_name: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_name?: string;
  email: string;
  phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  ein?: string;
  license_number?: string;
  license_state?: string;
  license_expiration?: string;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface Contractor {
  id: string;
  company_name: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_name?: string;
  email: string;
  phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  status: string;
}

export interface Certification {
  id: string;
  subcontractor_id: string;
  certification_type: string;
  certification_number?: string;
  issuing_authority?: string;
  issue_date?: string;
  expiration_date: string;
  status: string;
  document_url?: string;
  verification_status?: string;
}

export interface Violation {
  id: string;
  subcontractor_id: string;
  violation_type: string;
  description?: string;
  issued_date?: string;
  status: string;
  resolved_date?: string;
}

export interface ComplianceStatus {
  subcontractor_id: string;
  company_name: string;
  state?: string;
  compliance_score: number;
  status: string;
  active_certifications: number;
  expiring_certifications: number;
  expired_certifications: number;
  open_violations: number;
  resolved_violations: number;
}

export interface ComplianceAlert {
  id: string | number;
  type: 'critical' | 'warning' | 'info';
  message: string;
  certification_id?: string;
  subcontractor_id?: string;
  expiration_date?: string;
  days_until_expiration?: number;
}

export interface UploadStatus {
  upload_id: string;
  status: string;
  message: string;
  certification_id?: string;
}

export interface UploadResponse {
  id: string;
  subcontractor_id: string;
  certification_id?: string;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  mime_type: string;
  status: string;
  extraction_status: string;
  created_at: string;
  updated_at: string;
}

export const credentialsApi = {
  upload: (subcontractorId: string, file: File, certificationType: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('certification_type', certificationType);
    
    return fetch(`${API_BASE_URL}/subcontractors/${subcontractorId}/credentials/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      },
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error('Upload failed');
      return res.json();
    });
  },

  getUploads: (subcontractorId: string) =>
    apiClient.get<UploadResponse[]>(`/subcontractors/${subcontractorId}/credentials/uploads`),

  processUpload: (uploadId: string) =>
    apiClient.post<UploadStatus>(`/credentials/uploads/${uploadId}/process`),

  createCertification: (uploadId: string) =>
    apiClient.post<Certification>(`/credentials/uploads/${uploadId}/create-certification`),

  deleteUpload: (uploadId: string) =>
    apiClient.delete(`/credentials/uploads/${uploadId}`),
};

export interface DashboardSummary {
  total_subcontractors: number;
  active_subcontractors: number;
  compliance_rate: number;
  total_projects: number;
  active_projects: number;
  expiring_this_month: number;
  open_violations: number;
  recent_alerts: ComplianceAlert[];
}

export const dashboardApi = {
  getSummary: () => apiClient.get<DashboardSummary>('/dashboard/summary'),
};

export interface BillingPlan {
  plan: string;
  name: string;
  price: string;
  limit: number;
  features: string[];
}

export interface SubscriptionStatus {
  plan: string;
  status: string;
  current_period_end: string | null;
  subcontractor_limit: number;
  subcontractor_count: number;
  can_add_more: boolean;
}

export const billingApi = {
  getPlans: () => apiClient.get<BillingPlan[]>('/billing/plans'),
  getSubscription: () => apiClient.get<SubscriptionStatus>('/billing/subscription'),
  createCheckout: (plan: string) => apiClient.post<{ checkout_url: string }>('/billing/checkout', { plan }),
  createPortal: () => apiClient.post<{ portal_url: string }>('/billing/portal', {}),
};

export interface FeatureAdoptionData {
  feature_name: string;
  event_date?: string;
  total_events: number;
  unique_users: number;
  view_count: number;
  action_count: number;
  export_count: number;
  computed_at?: string;
}

export interface SystemHealthData {
  service_name: string;
  metric_name: string;
  metric_unit?: string;
  avg_value: number;
  min_value: number;
  max_value: number;
  p95_value: number;
  total_count: number;
  computed_at?: string;
}

export interface PerformanceMetricsData {
  requests_per_second: number;
  error_rate_percent: number;
  avg_response_time_ms: number;
  p50_response_time_ms: number;
  p95_response_time_ms: number;
  p99_response_time_ms: number;
  active_db_connections: number;
  max_db_connections: number;
  active_requests: number;
  rate_limit_hits: number;
  computed_at?: string;
}

export interface ComplianceTrendPoint {
  date?: string;
  active_subcontractors: number;
  valid_certifications: number;
  expired_certifications: number;
  open_violations: number;
  open_osha_violations: number;
  compliance_percentage: number;
  computed_at?: string;
}

export interface ComplianceSummaryData {
  total_subcontractors: number;
  active_subcontractors: number;
  suspended_subcontractors: number;
  blacklisted_subcontractors: number;
  compliant_subcontractors: number;
  compliance_rate: number;
  expiring_soon_30d: number;
  expiring_soon_60d: number;
  open_violations: number;
  open_osha_violations: number;
  total_open_penalties: number;
  valid_certifications: number;
  expired_certifications: number;
  pending_verification_certs: number;
  computed_at?: string;
}

export interface PilotEngagementData {
  total_organizations: number;
  active_organizations_30d: number;
  total_users: number | null;
  active_users_30d: number;
  avg_events_per_org: number;
  onboarding_completion_rate: number;
  feature_adoption_by_org: Record<string, number>;
  recently_active_orgs: Array<{
    organization_id: number;
    organization_name: string;
    last_activity: string;
  }>;
  engagement_trends: Array<{
    date: string;
    active_organizations: number;
    total_events: number;
  }>;
}

export interface DailyActiveUserData {
  day: string;
  active_users: number;
}

export interface AnalyticsEventRecord {
  id: string;
  event_type: string;
  user_id: string | null;
  organization_id: number | string | null;
  metadata: Record<string, unknown> | null;
  source_service: string | null;
  created_at: string;
}

export interface AnomalyRecord {
  type: string;
  severity: string;
  feature: string;
  message: string;
  detected_at: string;
  metric_value: number | null;
  expected_range: string | null;
}

export interface AnomaliesResponse {
  anomalies: AnomalyRecord[];
  total: number;
}

export interface WeeklyReportAlert {
  type: string;
  feature: string;
  message: string;
}

export interface WeeklyReportData {
  period: string;
  generated_at: string;
  feature_adoption: FeatureAdoptionData[];
  system_health: SystemHealthData[];
  alerts: WeeklyReportAlert[];
}

export interface AnalyticsEventFilters {
  organization_id?: string;
  event_type?: string;
  days?: number;
  skip?: number;
  limit?: number;
}

export const analyticsApi = {
  getFeatureAdoption: (params?: { feature_name?: string; days?: number; limit?: number; skip?: number }) =>
    apiClient.get<FeatureAdoptionData[]>('/analytics/feature-adoption', params?.limit || params?.skip ? { params: { ...(params.feature_name && { feature_name: params.feature_name }), ...(params.days && { days: String(params.days) }), ...(params.limit && { limit: String(params.limit) }), ...(params.skip && { skip: String(params.skip) }) } } : undefined),

  getSystemHealth: (params?: { service_name?: string; metric_name?: string; hours?: number }) =>
    apiClient.get<SystemHealthData[]>('/analytics/system-health', params?.service_name || params?.metric_name || params?.hours ? { params: { ...(params.service_name && { service_name: params.service_name }), ...(params.metric_name && { metric_name: params.metric_name }), ...(params.hours && { hours: String(params.hours) }) } } : undefined),

  getPerformanceMetrics: () =>
    apiClient.get<PerformanceMetricsData>('/analytics/performance'),

  getPilotEngagement: (days?: number) =>
    apiClient.get<PilotEngagementData>(`/analytics/pilot-engagement${days ? `?days=${days}` : ''}`),

  getDailyActiveUsers: (days?: number) =>
    apiClient.get<DailyActiveUserData[]>(`/analytics/daily-active-users${days ? `?days=${days}` : ''}`),

  getEvents: (filters: AnalyticsEventFilters = {}) => {
    const params: Record<string, string> = {};
    if (filters.organization_id) params.organization_id = filters.organization_id;
    if (filters.event_type) params.event_type = filters.event_type;
    if (filters.days !== undefined) params.days = String(filters.days);
    if (filters.skip !== undefined) params.skip = String(filters.skip);
    if (filters.limit !== undefined) params.limit = String(filters.limit);
    const hasParams = Object.keys(params).length > 0;
    return apiClient.get<AnalyticsEventRecord[]>('/analytics/events', hasParams ? { params } : undefined);
  },

  getAnomalies: () =>
    apiClient.get<AnomaliesResponse>('/analytics/anomalies'),

  getWeeklyReport: () =>
    apiClient.get<WeeklyReportData>('/analytics/weekly-report'),

  trackFeature: (featureName: string, eventType: string, metadata?: Record<string, unknown>) =>
    apiClient.post<{ status: string; event_id?: string }>('/analytics/track-feature', {
      feature_name: featureName,
      event_type: eventType,
      ...(metadata && { metadata }),
    }),
};

export const complianceAnalyticsApi = {
  getTrends: (days: number = 30) =>
    apiClient.get<ComplianceTrendPoint[]>(`/compliance/trends?days=${days}`),

  getSummary: () =>
    apiClient.get<ComplianceSummaryData>('/compliance/summary'),
};

export type EventType = 'page_view' | 'feature_usage' | 'onboarding_completion' | 'subcontractor_action' | 'cert_upload' | 'feedback_submit' | 'report_export';

export interface AnalyticsEvent {
  event_type: EventType;
  event_name: string;
  event_data?: Record<string, unknown>;
  page_url?: string;
  referrer_url?: string;
  duration_ms?: number;
}

export const analyticsTracker = {
  async track(event: AnalyticsEvent): Promise<{ id: string; status: string }> {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE_URL}/analytics/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify(event),
    });
    if (!response.ok) {
      console.warn('Analytics tracking failed:', response.statusText);
    }
    return response.json();
  },

  trackPageView(pageName: string, metadata?: Record<string, unknown>) {
    return this.track({
      event_type: 'page_view',
      event_name: pageName,
      event_data: metadata,
      page_url: window.location.pathname,
      referrer_url: document.referrer || undefined,
    });
  },

  trackFeatureUsage(featureName: string, action: string, metadata?: Record<string, unknown>) {
    return this.track({
      event_type: 'feature_usage',
      event_name: `${featureName}_${action}`,
      event_data: metadata,
      page_url: window.location.pathname,
    });
  },

  trackOnboarding(step: string, completed: boolean, metadata?: Record<string, unknown>) {
    return this.track({
      event_type: 'onboarding_completion',
      event_name: `onboarding_${step}`,
      event_data: { ...metadata, completed },
      page_url: window.location.pathname,
    });
  },

  trackSubcontractorAction(action: 'add' | 'edit' | 'delete' | 'view', subcontractorId: string, metadata?: Record<string, unknown>) {
    return this.track({
      event_type: 'subcontractor_action',
      event_name: `subcontractor_${action}`,
      event_data: { ...metadata, subcontractor_id: subcontractorId },
      page_url: window.location.pathname,
    });
  },

  trackCertUpload(subcontractorId: string, certificationType: string, success: boolean) {
    return this.track({
      event_type: 'cert_upload',
      event_name: 'certification_uploaded',
      event_data: { subcontractor_id: subcontractorId, certification_type: certificationType, success },
      page_url: window.location.pathname,
    });
  },

  trackFeedbackSubmit(feedbackType: string, hasRating: boolean) {
    return this.track({
      event_type: 'feedback_submit',
      event_name: 'feedback_submitted',
      event_data: { feedback_type: feedbackType, has_rating: hasRating },
      page_url: window.location.pathname,
    });
  },

  trackReportExport(reportType: string, format: 'csv' | 'pdf') {
    return this.track({
      event_type: 'report_export',
      event_name: `${reportType}_export`,
      event_data: { format },
      page_url: window.location.pathname,
    });
  },
};