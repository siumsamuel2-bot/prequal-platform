const API_BASE_URL = (typeof process !== 'undefined' && process.env && process.env.VITE_API_URL) || '/api';

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
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
      throw new Error(error.detail || `HTTP error ${response.status}`);
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
};

export const subcontractorApi = {
  getAll: () => apiClient.get<Subcontractor[]>('/subcontractors'),

  getById: (id: string) => apiClient.get<Subcontractor>(`/subcontractors/${id}`),

  create: (data: Omit<Subcontractor, 'id'>) =>
    apiClient.post<Subcontractor>('/subcontractors', data),

  update: (id: string, data: Partial<Subcontractor>) =>
    apiClient.put<Subcontractor>(`/subcontractors/${id}`, data),

  delete: (id: string) => apiClient.delete<{ message: string }>(`/subcontractors/${id}`),
};

export const complianceApi = {
  getStatus: () => apiClient.get<ComplianceStatus>('/compliance/status'),

  getAlerts: () => apiClient.get<ComplianceAlert[]>('/compliance/alerts'),
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