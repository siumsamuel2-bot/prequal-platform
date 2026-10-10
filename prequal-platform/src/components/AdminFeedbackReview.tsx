import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { feedbackApi, FeedbackSubmission, FeedbackStatus, ApiError } from '../api/client';
import { isForbiddenError, NoAccessState } from './NoAccessState';
import { EmptyState, Loading } from './Loading';
import { isAdmin } from '../utils/auth';
import { useToast } from './ToastContext';

const STATUS_OPTIONS: FeedbackStatus[] = ['new', 'triaged', 'declined', 'duplicate', 'resolved'];
const TYPE_FILTERS = ['all', 'rating', 'comment', 'support'];
const STATUS_FILTERS = ['all', 'new', 'triaged', 'declined', 'duplicate', 'resolved'];

const STATUS_LABELS: Record<FeedbackStatus, string> = {
  new: 'New',
  triaged: 'Triaged',
  declined: 'Declined',
  duplicate: 'Duplicate',
  resolved: 'Resolved',
};

interface RowDraft {
  status: FeedbackStatus;
  note: string;
}

const AdminFeedbackReview = () => {
  const toast = useToast();
  const isAdminUser = isAdmin();
  const [submissions, setSubmissions] = useState<FeedbackSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const loadSubmissions = useCallback(async () => {
    if (!isAdminUser) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const response = await feedbackApi.list({
        ...(statusFilter !== 'all' && { status: statusFilter }),
        ...(typeFilter !== 'all' && { type: typeFilter }),
      });
      setSubmissions(response.items ?? []);
      setDenied(false);
    } catch (err) {
      if (isForbiddenError(err)) {
        // Fail closed: the server disagrees with the local role state.
        setDenied(true);
        setSubmissions([]);
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Failed to load feedback submissions');
      }
    } finally {
      setLoading(false);
    }
  }, [isAdminUser, statusFilter, typeFilter, toast]);

  useEffect(() => {
    loadSubmissions();
  }, [loadSubmissions]);

  if (!isAdminUser) {
    return (
      <div className="admin-feedback-review" style={{ padding: '24px' }}>
        <h1>Feedback Review</h1>
        <NoAccessState variant="no-access" />
      </div>
    );
  }

  const draftFor = (submission: FeedbackSubmission): RowDraft =>
    drafts[submission.id] ?? {
      status: submission.status,
      note: submission.disposition_note ?? '',
    };

  const setDraft = (submission: FeedbackSubmission, patch: Partial<RowDraft>) => {
    setDrafts((prev) => ({
      ...prev,
      [submission.id]: { ...draftFor(submission), ...patch },
    }));
  };

  const saveDisposition = async (submission: FeedbackSubmission) => {
    const draft = draftFor(submission);
    if ((draft.status === 'declined' || draft.status === 'duplicate') && !draft.note.trim()) {
      toast.error('A note is required when declining or marking a duplicate.');
      return;
    }
    setSavingId(submission.id);
    try {
      const updated = await feedbackApi.update(submission.id, {
        status: draft.status,
        disposition_note: draft.note.trim() || null,
      });
      setSubmissions((prev) => prev.map((s) => (s.id === submission.id ? { ...s, ...updated } : s)));
      toast.success(`Submission marked as ${STATUS_LABELS[draft.status].toLowerCase()}.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to update the submission.');
    } finally {
      setSavingId(null);
    }
  };

  const formatDate = (value: string) => new Date(value).toLocaleString('en-US');

  return (
    <div className="admin-feedback-review" style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#111827', margin: '0 0 4px' }}>Feedback Review</h1>
          <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>
            Organization-scoped submissions with disposition actions
          </p>
        </div>
        <button
          type="button"
          onClick={loadSubmissions}
          disabled={loading}
          aria-label="Refresh feedback submissions"
          style={{
            border: '1px solid #d1d5db',
            background: '#ffffff',
            color: '#374151',
            cursor: loading ? 'default' : 'pointer',
            fontSize: '13px',
            padding: '8px 14px',
            borderRadius: '6px',
          }}
        >
          {loading ? 'Refreshing...' : 'â†» Refresh'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '12px', margin: '16px 0', flexWrap: 'wrap' }}>
        <label htmlFor="feedback-status-filter" style={{ fontSize: '13px', color: '#374151', alignSelf: 'center' }}>
          Status:
        </label>
        <select
          id="feedback-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="filter-select"
          aria-label="Filter by status"
          style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All' : STATUS_LABELS[s as FeedbackStatus]}
            </option>
          ))}
        </select>
        <label htmlFor="feedback-type-filter" style={{ fontSize: '13px', color: '#374151', alignSelf: 'center' }}>
          Type:
        </label>
        <select
          id="feedback-type-filter"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="filter-select"
          aria-label="Filter by type"
          style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
        >
          {TYPE_FILTERS.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All' : t}
            </option>
          ))}
        </select>
      </div>

      {denied ? (
        <NoAccessState variant="no-access" />
      ) : loading && submissions.length === 0 ? (
        <Loading message="Loading feedback submissions..." />
      ) : submissions.length === 0 ? (
        <EmptyState
          title="No feedback submissions yet"
          description="Submissions from the feedback widget, dashboards, and support form will appear here."
        />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px',
              backgroundColor: '#ffffff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
            }}
          >
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                <th style={thStyle}>Received</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Surface</th>
                <th style={thStyle}>Rating</th>
                <th style={thStyle}>Message</th>
                <th style={thStyle}>Disposition</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((submission) => {
                const draft = draftFor(submission);
                const needsNote = draft.status === 'declined' || draft.status === 'duplicate';
                const changed =
                  draft.status !== submission.status || draft.note !== (submission.disposition_note ?? '');
                return (
                  <tr key={submission.id} style={{ borderBottom: '1px solid #f3f4f6', verticalAlign: 'top' }}>
                    <td style={tdStyle}>{formatDate(submission.created_at)}</td>
                    <td style={tdStyle}>{submission.type}</td>
                    <td style={tdStyle}>{submission.surface}</td>
                    <td style={tdStyle}>{submission.rating ?? 'â€”'}</td>
                    <td style={{ ...tdStyle, maxWidth: '280px' }}>
                      {submission.message ? (
                        <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{submission.message}</span>
                      ) : (
                        <span style={{ color: '#9ca3af' }}>â€”</span>
                      )}
                    </td>
                    <td style={{ ...tdStyle, minWidth: '220px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <select
                          id={`disposition-${submission.id}`}
                          value={draft.status}
                          onChange={(e) => setDraft(submission, { status: e.target.value as FeedbackStatus })}
                          aria-label={`Disposition for ${submission.type} submission`}
                          disabled={savingId === submission.id}
                          style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {STATUS_LABELS[s]}
                            </option>
                          ))}
                        </select>
                        {needsNote && (
                          <input
                            type="text"
                            value={draft.note}
                            onChange={(e) => setDraft(submission, { note: e.target.value })}
                            placeholder="Note (required)"
                            aria-label="Disposition note"
                            maxLength={500}
                            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                          />
                        )}
                        <button
                          type="button"
                          onClick={() => saveDisposition(submission)}
                          disabled={!changed || savingId === submission.id}
                          aria-label={`Save disposition for ${submission.type} submission`}
                          style={{
                            alignSelf: 'flex-start',
                            border: 'none',
                            background: changed ? '#3b82f6' : '#e5e7eb',
                            color: changed ? '#ffffff' : '#9ca3af',
                            cursor: changed ? 'pointer' : 'default',
                            fontSize: '12px',
                            fontWeight: 500,
                            padding: '6px 12px',
                            borderRadius: '6px',
                          }}
                        >
                          {savingId === submission.id ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const thStyle: CSSProperties = {
  padding: '10px 12px',
  fontSize: '12px',
  fontWeight: 600,
  color: '#6b7280',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  backgroundColor: '#f9fafb',
};

const tdStyle: CSSProperties = {
  padding: '10px 12px',
  color: '#374151',
};

export default AdminFeedbackReview;
