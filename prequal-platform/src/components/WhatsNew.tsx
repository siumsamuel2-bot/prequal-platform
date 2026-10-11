import { useCallback, useEffect, useRef } from 'react';
import { Badge } from './ui';
import { RELEASE_NOTES, type ReleaseCategory, type ReleaseNote } from '../data/releaseNotes';
import './WhatsNew.css';

interface WhatsNewProps {
  isOpen: boolean;
  onClose: () => void;
  notes?: ReleaseNote[];
}

const CATEGORY_VARIANT: Record<ReleaseCategory, 'success' | 'info' | 'warning' | 'danger'> = {
  Added: 'success',
  Changed: 'info',
  Fixed: 'warning',
  Security: 'danger',
};

const formatDate = (iso: string): string => {
  const parsed = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  });
};

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Right-side "What's New" drawer rendering bundled release notes (MID-669).
 *
 * Accessible dialog semantics: role=dialog + aria-modal, labelled heading,
 * a focus trap, Escape-to-close, focus restore, and scroll lock. Responsive
 * (full-width on small screens). No backend; content is static for v1.
 */
export const WhatsNew = ({ isOpen, onClose, notes = RELEASE_NOTES }: WhatsNewProps) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusable = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey) {
        if (document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;

    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    const focusable = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    (focusable && focusable.length > 0 ? focusable[0] : panelRef.current)?.focus();

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
      previouslyFocusedRef.current?.focus();
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div
      className="whats-new-root"
      role="dialog"
      aria-modal="true"
      aria-labelledby="whats-new-title"
    >
      <div className="whats-new-overlay" onClick={onClose} aria-hidden="true" />
      <div className="whats-new-panel" ref={panelRef} tabIndex={-1}>
        <header className="whats-new-header">
          <div>
            <h2 id="whats-new-title" className="whats-new-title">
              What&apos;s New
            </h2>
            <p className="whats-new-subtitle">The latest improvements to Prequal.</p>
          </div>
          <button
            type="button"
            className="whats-new-close"
            onClick={onClose}
            aria-label="Close What's New"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
            </svg>
          </button>
        </header>

        <div className="whats-new-body">
          {notes.length === 0 ? (
            <div className="whats-new-empty">
              <div className="whats-new-empty-icon" aria-hidden="true">
                🚀
              </div>
              <p className="whats-new-empty-title">You&apos;re all caught up</p>
              <p className="whats-new-empty-text">
                Release notes will appear here as we ship improvements.
              </p>
            </div>
          ) : (
            notes.map((note) => (
              <article key={note.version} className="whats-new-release">
                <div className="whats-new-release-head">
                  <span className="whats-new-version">v{note.version}</span>
                  <Badge variant="info" size="sm">
                    {formatDate(note.date)}
                  </Badge>
                </div>
                <h3 className="whats-new-release-title">{note.title}</h3>
                {note.summary && (
                  <p className="whats-new-release-summary">{note.summary}</p>
                )}
                {note.changes.map((change) => (
                  <section key={change.category} className="whats-new-change">
                    <Badge variant={CATEGORY_VARIANT[change.category]} size="sm">
                      {change.category}
                    </Badge>
                    <ul className="whats-new-change-list">
                      {change.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </section>
                ))}
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default WhatsNew;
