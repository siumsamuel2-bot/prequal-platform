import { useCallback } from 'react';
import { apiClient } from '../api/client';

interface AnalyticsEvent {
  event_type: string;
  event_name: string;
  event_data?: Record<string, any>;
  page_url?: string;
  referrer_url?: string;
  duration_ms?: number;
}

export function useAnalytics() {
  const trackEvent = useCallback(async (event: AnalyticsEvent) => {
    try {
      await apiClient.post('/analytics/events', event);
    } catch (error) {
      console.error('Failed to track analytics event:', error);
    }
  }, []);

  const trackPageView = useCallback((pageUrl: string, referrerUrl?: string) => {
    trackEvent({
      event_type: 'page_view',
      event_name: 'page_view',
      page_url: pageUrl,
      referrer_url: referrerUrl
    });
  }, [trackEvent]);

  const trackFeatureUsage = useCallback((featureName: string, metadata?: Record<string, any>) => {
    trackEvent({
      event_type: 'feature_usage',
      event_name: featureName,
      event_data: metadata
    });
  }, [trackEvent]);

  const trackOnboardingStep = useCallback((step: string, completed: boolean) => {
    trackEvent({
      event_type: 'onboarding_step',
      event_name: `onboarding_${step}`,
      event_data: { completed }
    });
  }, [trackEvent]);

  const trackCertificationUpload = useCallback((subcontractorId: string, certificationType: string) => {
    trackEvent({
      event_type: 'certification_upload',
      event_name: 'certification_upload',
      event_data: { subcontractor_id: subcontractorId, certification_type: certificationType }
    });
  }, [trackEvent]);

  const trackSubcontractorAction = useCallback((action: 'add' | 'edit' | 'delete', subcontractorId: string) => {
    trackEvent({
      event_type: `subcontractor_${action}`,
      event_name: `subcontractor_${action}`,
      event_data: { subcontractor_id: subcontractorId }
    });
  }, [trackEvent]);

  const trackSearch = useCallback((searchTerm: string, resultsCount: number) => {
    trackEvent({
      event_type: 'search',
      event_name: 'search',
      event_data: { search_term: searchTerm, results_count: resultsCount }
    });
  }, [trackEvent]);

  const trackExport = useCallback((exportType: string, format: string) => {
    trackEvent({
      event_type: 'export',
      event_name: `export_${exportType}`,
      event_data: { format }
    });
  }, [trackEvent]);

  const trackFeedback = useCallback((feedbackType: string, rating?: number) => {
    trackEvent({
      event_type: 'feedback_submit',
      event_name: `feedback_${feedbackType}`,
      event_data: { rating }
    });
  }, [trackEvent]);

  return {
    trackEvent,
    trackPageView,
    trackFeatureUsage,
    trackOnboardingStep,
    trackCertificationUpload,
    trackSubcontractorAction,
    trackSearch,
    trackExport,
    trackFeedback
  };
}