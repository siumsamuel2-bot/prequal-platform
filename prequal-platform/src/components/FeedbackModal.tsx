import { useState } from 'react';
import { apiClient } from '../api/client';
import { useToast } from './ToastContext';
import { useAnalytics } from '../hooks/useAnalytics';
import './FeedbackModal.css';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type FeedbackType = 'feature_request' | 'bug_report' | 'general' | 'rating';

const FEEDBACK_TYPES: { value: FeedbackType; label: string; icon: string }[] = [
  { value: 'feature_request', label: 'Feature Request', icon: '💡' },
  { value: 'bug_report', label: 'Bug Report', icon: '🐛' },
  { value: 'general', label: 'General Feedback', icon: '💬' },
  { value: 'rating', label: 'Rating', icon: '⭐' },
];

export const FeedbackModal = ({ isOpen, onClose }: FeedbackModalProps) => {
  const toast = useToast();
  const { trackFeedback } = useAnalytics();
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('general');
  const [rating, setRating] = useState<number | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!body.trim()) {
      toast.error('Please provide feedback details');
      return;
    }

    if (feedbackType === 'rating' && !rating) {
      toast.error('Please select a rating');
      return;
    }

    setIsSubmitting(true);
    try {
      await apiClient.post('/feedback', {
        feedback_type: feedbackType,
        rating: rating,
        subject: subject || undefined,
        body: body.trim(),
      });
      
      trackFeedback(feedbackType, rating || undefined);
      toast.success('Thank you for your feedback!');
      handleClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setFeedbackType('general');
    setRating(null);
    setSubject('');
    setBody('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content feedback-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Share Your Feedback</h2>
          <button className="close-btn" onClick={handleClose}>×</button>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="feedback-types">
            {FEEDBACK_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                className={`feedback-type-btn ${feedbackType === type.value ? 'selected' : ''}`}
                onClick={() => setFeedbackType(type.value)}
              >
                <span className="type-icon">{type.icon}</span>
                <span className="type-label">{type.label}</span>
              </button>
            ))}
          </div>

          {feedbackType === 'rating' && (
            <div className="rating-section">
              <label>How would you rate your experience?</label>
              <div className="star-rating">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${rating && star <= rating ? 'active' : ''}`}
                    onClick={() => setRating(star)}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="feedback-subject">Subject (optional)</label>
            <input
              id="feedback-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Brief summary of your feedback"
              maxLength={200}
            />
          </div>

          <div className="form-group">
            <label htmlFor="feedback-body">Details *</label>
            <textarea
              id="feedback-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Tell us more about your experience or suggestion..."
              rows={5}
              required
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="cancel-btn" onClick={handleClose}>
              Cancel
            </button>
            <button type="submit" className="submit-btn" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FeedbackModal;