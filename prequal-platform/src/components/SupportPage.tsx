import { useState } from 'react';
import { feedbackApi, ApiError } from '../api/client';
import { isForbiddenError, NoAccessState } from './NoAccessState';
import { useToast } from './ToastContext';

const SUPPORT_EMAIL = 'support@prequal.app';
const RESPONSE_EXPECTATION = 'We reply to support requests within one business day.';

interface KnownIssue {
  title: string;
  detail: string;
  reportedAt: string;
}

const KNOWN_ISSUES: KnownIssue[] = [
  {
    title: 'Platform analytics panels are admin-only',
    detail:
      'Feature adoption, system health, performance, and platform-wide compliance aggregates are restricted to administrator accounts. Team members see their own team-scoped data instead.',
    reportedAt: '2026-10-09',
  },
  {
    title: 'State credential syncs can lag behind state databases',
    detail:
      'Verification records pulled from state credential databases refresh on a periodic schedule, so very recent changes at the source may not appear immediately.',
    reportedAt: '2026-10-09',
  },
  {
    title: 'Certificate uploads need a clear scan',
    detail:
      'OCR extraction of uploaded certifications works best with a straight, well-lit scan. Blurry photos may need the expiration date corrected by hand.',
    reportedAt: '2026-10-09',
  },
];

const SupportPage = () => {
  const toast = useToast();
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [denied, setDenied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || submitting) return;
    setSubmitting(true);
    try {
      await feedbackApi.submit({
        type: 'support',
        surface: 'contact_page',
        page_url: window.location.pathname,
        message: message.trim(),
      });
      setMessage('');
      toast.success('Support request sent. We will get back to you within one business day.');
    } catch (err) {
      if (isForbiddenError(err)) {
        setDenied(true);
      } else {
        const detail = err instanceof ApiError ? err.message : 'Failed to send your request. Please try again.';
        toast.error(detail);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (denied) {
    return (
      <div className="support-page" style={{ padding: '24px' }}>
        <h1>Support</h1>
        <NoAccessState variant="no-access" title="Support requests are unavailable for your account" />
      </div>
    );
  }

  return (
    <div className="support-page" style={{ padding: '24px', maxWidth: '880px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#111827', margin: '0 0 4px' }}>Support</h1>
      <p style={{ fontSize: '14px', color: '#6b7280', margin: '0 0 24px' }}>
        Questions, problems, or suggestions? We want to hear them.
      </p>

      <section aria-label="Contact options" style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: '0 0 8px' }}>Contact us</h2>
        <p style={{ fontSize: '14px', color: '#374151', margin: '0 0 12px' }}>
          Email us at{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: '#3b82f6' }}>
            {SUPPORT_EMAIL}
          </a>{' '}
          — {RESPONSE_EXPECTATION}
        </p>
        <form
          onSubmit={handleSubmit}
          aria-label="Support request form"
          style={{
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            padding: '16px',
            backgroundColor: '#ffffff',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            maxWidth: '560px',
          }}
        >
          <label htmlFor="support-message" style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
            Or send a message from here
          </label>
          <textarea
            id="support-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            maxLength={4000}
            placeholder="Describe what you need help with..."
            aria-label="Support message"
            required
            style={{
              width: '100%',
              padding: '10px 12px',
              fontSize: '14px',
              fontFamily: 'inherit',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              boxSizing: 'border-box',
              resize: 'vertical',
            }}
          />
          <div>
            <button
              type="submit"
              disabled={submitting}
              aria-label="Send support request"
              style={{
                border: 'none',
                background: '#3b82f6',
                color: '#ffffff',
                cursor: submitting ? 'default' : 'pointer',
                fontSize: '14px',
                fontWeight: 500,
                padding: '8px 16px',
                borderRadius: '6px',
                opacity: submitting ? 0.7 : 1,
              }}
            >
              {submitting ? 'Sending...' : 'Send request'}
            </button>
          </div>
        </form>
      </section>

      <section aria-label="Known issues">
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: '0 0 8px' }}>Known issues</h2>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {KNOWN_ISSUES.map((issue) => (
            <li
              key={issue.title}
              style={{
                border: '1px solid #f3f4f6',
                borderRadius: '8px',
                padding: '12px 16px',
                backgroundColor: '#f9fafb',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#374151', margin: 0 }}>{issue.title}</h3>
                <span style={{ fontSize: '12px', color: '#9ca3af' }}>Updated {issue.reportedAt}</span>
              </div>
              <p style={{ fontSize: '13px', color: '#6b7280', margin: '6px 0 0', lineHeight: 1.5 }}>{issue.detail}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};

export default SupportPage;
