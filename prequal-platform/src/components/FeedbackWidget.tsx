import React, { useState } from 'react';
import { feedbackApi } from '../api/client';
import { Link } from 'react-router-dom';

interface FeedbackWidgetProps {
  surface: string;
}

type WidgetPhase = 'idle' | 'message' | 'submitting' | 'submitted' | 'error';

const FeedbackWidget: React.FC<FeedbackWidgetProps> = ({ surface }) => {
  const [phase, setPhase] = useState<WidgetPhase>('idle');
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  const submit = async (chosenRating: number, text: string) => {
    setPhase('submitting');
    try {
      // Optimistic: the thank-you state shows while the request is in flight.
      setPhase('submitted');
      await feedbackApi.submit({
        type: 'rating',
        surface,
        page_url: window.location.pathname,
        rating: chosenRating,
        ...(text.trim() ? { message: text.trim() } : {}),
      });
    } catch {
      // Graceful: surface a single inline retry, never a toast storm.
      setPhase('error');
    }
  };

  const handleThumb = (value: number) => {
    setRating(value);
    setPhase('message');
  };

  const handleSend = () => {
    if (rating === null) return;
    submit(rating, message);
  };

  const handleDismiss = () => {
    setPhase('idle');
    setRating(null);
    setMessage('');
  };

  return (
    <div
      className="feedback-widget"
      style={{
        position: 'fixed',
        bottom: '16px',
        right: '16px',
        zIndex: 900,
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '12px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
        padding: '12px 16px',
        maxWidth: '320px',
        width: 'calc(100% - 32px)',
        boxSizing: 'border-box',
        fontFamily: 'inherit',
      }}
    >
      {phase === 'idle' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <span style={{ fontSize: '13px', color: '#374151' }}>How is this dashboard working for you?</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => handleThumb(5)}
              aria-label="This dashboard works well"
              style={{
                border: '1px solid #d1d5db',
                background: '#ffffff',
                borderRadius: '6px',
                padding: '6px 10px',
                cursor: 'pointer',
                fontSize: '14px',
                lineHeight: 1,
              }}
            >
              👍
            </button>
            <button
              type="button"
              onClick={() => handleThumb(1)}
              aria-label="This dashboard needs work"
              style={{
                border: '1px solid #d1d5db',
                background: '#ffffff',
                borderRadius: '6px',
                padding: '6px 10px',
                cursor: 'pointer',
                fontSize: '14px',
                lineHeight: 1,
              }}
            >
              👎
            </button>
          </div>
        </div>
      )}

      {(phase === 'message' || phase === 'submitting' || phase === 'error') && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
        >
          <label htmlFor="feedback-widget-message" style={{ fontSize: '13px', color: '#374151', fontWeight: 500 }}>
            {rating === 1 ? 'What needs work? (optional)' : 'Anything to add? (optional)'}
          </label>
          <textarea
            id="feedback-widget-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={1000}
            rows={3}
            aria-label="Feedback message"
            style={{
              width: '100%',
              padding: '8px 10px',
              fontSize: '13px',
              fontFamily: 'inherit',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              boxSizing: 'border-box',
              resize: 'vertical',
            }}
          />
          {phase === 'error' && (
            <p role="alert" style={{ margin: 0, fontSize: '12px', color: '#ef4444' }}>
              Could not send your feedback. Please try again.
            </p>
          )}
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={handleDismiss}
              style={{
                border: 'none',
                background: 'transparent',
                color: '#6b7280',
                cursor: 'pointer',
                fontSize: '12px',
                padding: '6px 8px',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={phase === 'submitting'}
              aria-label="Send feedback"
              style={{
                border: 'none',
                background: '#3b82f6',
                color: '#ffffff',
                cursor: phase === 'submitting' ? 'default' : 'pointer',
                fontSize: '12px',
                fontWeight: 500,
                padding: '6px 12px',
                borderRadius: '6px',
                opacity: phase === 'submitting' ? 0.7 : 1,
              }}
            >
              {phase === 'submitting' ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      )}

      {phase === 'submitted' && (
        <div role="status" aria-live="polite" style={{ textAlign: 'center' }}>
          <p style={{ margin: '0 0 6px', fontSize: '13px', fontWeight: 500, color: '#374151' }}>
            Thanks — your feedback was sent.
          </p>
          <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#6b7280' }}>
            Need help now?{' '}
            <Link to="/support" style={{ color: '#3b82f6' }}>
              Contact support
            </Link>
          </p>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="Dismiss feedback widget"
            style={{
              border: 'none',
              background: 'transparent',
              color: '#6b7280',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '4px 8px',
            }}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
};

export default FeedbackWidget;
