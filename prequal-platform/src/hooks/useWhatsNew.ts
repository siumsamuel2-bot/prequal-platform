import { useCallback, useState } from 'react';
import { getLatestVersion } from '../data/releaseNotes';

/** localStorage key holding the last release version the user acknowledged. */
export const WHATS_NEW_STORAGE_KEY = 'prequal.whatsNew.seenVersion';

function readSeenVersion(): string | null {
  try {
    return window.localStorage.getItem(WHATS_NEW_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeSeenVersion(version: string): void {
  try {
    window.localStorage.setItem(WHATS_NEW_STORAGE_KEY, version);
  } catch {
    // Storage can be unavailable (private mode); the "new" dot just reappears.
  }
}

export interface UseWhatsNewResult {
  /** Latest available release version ('' when there are no notes). */
  latestVersion: string;
  /** True when the latest version has not been acknowledged yet. */
  hasUnseen: boolean;
  /** Persist the latest version as seen (clears the unseen dot). */
  acknowledge: () => void;
}

/**
 * Tracks whether the user has seen the latest release notes.
 *
 * Acknowledgement is stored in localStorage only (no server state), so the
 * "new" indicator is per-browser and clears as soon as the surface is opened.
 */
export function useWhatsNew(): UseWhatsNewResult {
  const latestVersion = getLatestVersion();
  const [seenVersion, setSeenVersion] = useState<string | null>(readSeenVersion);

  const acknowledge = useCallback(() => {
    if (!latestVersion) return;
    writeSeenVersion(latestVersion);
    setSeenVersion(latestVersion);
  }, [latestVersion]);

  const hasUnseen = Boolean(latestVersion) && seenVersion !== latestVersion;

  return { latestVersion, hasUnseen, acknowledge };
}
