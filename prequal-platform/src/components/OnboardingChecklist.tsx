import { useState, useEffect } from 'react';
import { organizationApi, OnboardingStatus } from '../api/client';
import './OnboardingChecklist.css';

interface OnboardingChecklistProps {
  onComplete?: () => void;
}

export const OnboardingChecklist = ({ onComplete }: OnboardingChecklistProps) => {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await organizationApi.getOnboardingStatus();
        setStatus(data);
        if (data.step === 0 && onComplete) {
          onComplete();
        }
      } catch (err) {
        console.error('Failed to fetch onboarding status:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
  }, [onComplete]);

  if (loading) return null;
  if (!status || status.step === 0) return null;

  const tasks = [
    {
      step: 1,
      title: 'Set up your organization',
      description: 'Configure your company profile',
      icon: '🏢',
      link: '/setup',
      completed: status.has_organization,
    },
    {
      step: 2,
      title: 'Create your first project',
      description: 'Add a construction project to track',
      icon: '🚧',
      link: '/projects/new',
      completed: status.has_project,
    },
    {
      step: 3,
      title: 'Add subcontractors',
      description: 'Import or add your first subcontractor',
      icon: '👥',
      link: '/subcontractors/import',
      completed: status.has_subcontractor,
    },
  ];

  const activeTasks = tasks.filter((t) => !t.completed);
  const completedTasks = tasks.filter((t) => t.completed);

  return (
    <div className="onboarding-checklist">
      <div className="checklist-header">
        <h3>Get Started with Prequal</h3>
        <span className="progress-text">
          {completedTasks.length} of {tasks.length} completed
        </span>
      </div>

      <div className="checklist-progress">
        <div
          className="progress-bar"
          style={{ width: `${(completedTasks.length / tasks.length) * 100}%` }}
        />
      </div>

      <div className="checklist-tasks">
        {activeTasks.map((task) => (
          <a key={task.step} href={task.link} className="task-item">
            <span className="task-icon">{task.icon}</span>
            <div className="task-content">
              <span className="task-title">{task.title}</span>
              <span className="task-description">{task.description}</span>
            </div>
            <span className="task-arrow">→</span>
          </a>
        ))}
      </div>

      {activeTasks.length === 0 && (
        <div className="checklist-complete">
          <span className="complete-icon">✓</span>
          <span>You're all set! Your dashboard is ready.</span>
        </div>
      )}
    </div>
  );
};

export default OnboardingChecklist;