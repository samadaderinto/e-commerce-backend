'use client';

import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Bell, BellOff, CheckCircle2, CircleAlert, Moon, Sun } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useShop } from './providers';
import { api } from '@/lib/api';
import {
  fetchPushDeviceStatus,
  getFirebaseMessaging,
  pushDeviceChangeEvent,
  registerPushDevice,
  unregisterPushDevice,
} from '@/lib/firebase-messaging';
import Link from 'next/link';
import type { User } from '@/lib/types';

type Theme = 'light' | 'dark' | 'system';
type Appearance = 'light' | 'dark';

const normalize = (value: string | null): Theme =>
  value === 'light' || value === 'dark' ? value : 'system';

const scheduledAppearance = (): Appearance =>
  new Date().getHours() >= 6 && new Date().getHours() < 18 ? 'light' : 'dark';

type ThemeContextType = {
  preference: Theme;
  appearance: Appearance;
  change: (value: Theme) => void;
  toggle: () => void;
};

const ThemeContext = createContext<ThemeContextType | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<Theme>('system');
  const [appearance, setAppearance] = useState<Appearance>('light');
  const preferenceRef = useRef<Theme>('system');
  const scheduleRef = useRef<Appearance>('light');

  function apply(value: Appearance) {
    document.documentElement.dataset.theme = value;
    setAppearance(value);
  }

  useEffect(() => {
    try {
      preferenceRef.current = normalize(localStorage.getItem('proace-theme'));
    } catch {}
    setPreference(preferenceRef.current);
    scheduleRef.current = scheduledAppearance();
    apply(preferenceRef.current === 'system' ? scheduleRef.current : preferenceRef.current);

    const checkSchedule = () => {
      let saved = preferenceRef.current;
      try {
        saved = normalize(localStorage.getItem('proace-theme'));
      } catch {}
      const next = scheduledAppearance();
      if (saved !== preferenceRef.current || next !== scheduleRef.current) {
        preferenceRef.current = saved;
        setPreference(saved);
        scheduleRef.current = next;
        apply(saved === 'system' ? next : saved);
      }
    };

    const sync = (event: StorageEvent) => {
      if (event.key !== 'proace-theme' && event.key !== null) return;
      checkSchedule();
    };

    const interval = window.setInterval(checkSchedule, 1000);
    window.addEventListener('storage', sync);
    window.addEventListener('focus', checkSchedule);
    document.addEventListener('visibilitychange', checkSchedule);

    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', sync);
      window.removeEventListener('focus', checkSchedule);
      document.removeEventListener('visibilitychange', checkSchedule);
    };
  }, []);

  function change(value: Theme) {
    preferenceRef.current = value;
    setPreference(value);
    try {
      localStorage.setItem('proace-theme', value);
    } catch {}
    scheduleRef.current = scheduledAppearance();
    apply(value === 'system' ? scheduleRef.current : value);
  }

  const toggle = () =>
    change(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

  return (
    <ThemeContext.Provider value={{ preference, appearance, change, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('ThemeProvider missing');
  }
  return context;
}

export function ThemeToggle() {
  const { appearance, toggle } = useTheme();
  const label = appearance === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <button
      type="button"
      className="icon-button theme-toggle"
      aria-label={label}
      title={label}
      onClick={toggle}
    >
      {appearance === 'dark' ? <Sun size={21} /> : <Moon size={21} />}
    </button>
  );
}

export function AppearanceSettings() {
  const { preference, change } = useTheme();

  return (
    <section className="appearance-settings">
      <h2>Default appearance</h2>
      <p>Choose the appearance used throughout the app. Your preference is saved on this browser.</p>
      <fieldset>
        <legend className="sr-only">Default appearance</legend>
        {(['light', 'dark', 'system'] as const).map((value) => (
          <label
            className={`appearance-option ${preference === value ? 'active' : ''}`}
            key={value}
          >
            <input
              type="radio"
              name="default-appearance"
              value={value}
              checked={preference === value}
              onChange={() => change(value)}
            />
            <span>
              <strong>
                {value === 'system' ? 'System' : value === 'light' ? 'Light' : 'Dark'}
              </strong>
              <small>
                {value === 'system'
                  ? 'Light 6 a.m.–6 p.m.; dark 6 p.m.–6 a.m., in your local time.'
                  : `Always start in ${value} mode.`}
              </small>
            </span>
          </label>
        ))}
      </fieldset>
      <p className="muted">
        The header icon saves your light or dark choice too. Changes apply across all tabs in this browser.
      </p>
    </section>
  );
}

export function EmailPreferencesSettings() {
  const { user, notify } = useShop();
  const queryClient = useQueryClient();
  const [recommendations, setRecommendations] = useState(
    user?.email_product_recommendations ?? true
  );
  const [marketing, setMarketing] = useState(
    user?.email_marketing ?? false
  );
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setRecommendations(user.email_product_recommendations ?? true);
      setMarketing(user.email_marketing ?? false);
    }
  }, [user?.email_product_recommendations, user?.email_marketing]);

  if (!user) return null;

  async function updatePreference(
    key: 'email_product_recommendations' | 'email_marketing',
    nextValue: boolean
  ) {
    const prevRec = recommendations;
    const prevMkt = marketing;

    if (key === 'email_product_recommendations') setRecommendations(nextValue);
    if (key === 'email_marketing') setMarketing(nextValue);
    setSavingKey(key);

    try {
      const updated = await api<User>('me', 'PATCH', { [key]: nextValue });
      queryClient.setQueryData(['me'], updated);
      notify(
        key === 'email_product_recommendations'
          ? nextValue
            ? 'Product recommendation emails enabled.'
            : 'Product recommendation emails disabled.'
          : nextValue
            ? 'Marketing and promotional emails enabled.'
            : 'Marketing and promotional emails disabled.'
      );
    } catch (error) {
      if (key === 'email_product_recommendations') setRecommendations(prevRec);
      if (key === 'email_marketing') setMarketing(prevMkt);
      notify((error as Error).message, true);
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <section
      className="appearance-settings email-preferences-settings"
      aria-label="Email and marketing preferences"
    >
      <h2>Email communication preferences</h2>
      <p>
        Choose which optional emails you would like to receive. Critical account receipts, order tracking updates, and security notices will always be sent.
      </p>
      <fieldset>
        <legend className="sr-only">Email communication preferences</legend>
        <label className={`appearance-option ${recommendations ? 'active' : ''}`}>
          <input
            type="checkbox"
            name="email_product_recommendations"
            checked={recommendations}
            disabled={savingKey !== null}
            onChange={(e) =>
              void updatePreference('email_product_recommendations', e.target.checked)
            }
          />
          <span>
            <strong>Product recommendations</strong>
            <small>
              Curated picks, related items, and special recommendations tailored to products you view, save, or purchase.
            </small>
          </span>
        </label>
        <label className={`appearance-option ${marketing ? 'active' : ''}`}>
          <input
            type="checkbox"
            name="email_marketing"
            checked={marketing}
            disabled={savingKey !== null}
            onChange={(e) =>
              void updatePreference('email_marketing', e.target.checked)
            }
          />
          <span>
            <strong>Marketing & promotions</strong>
            <small>
              Seasonal sales, exclusive merchant discount drops, official partner spotlights, and platform updates.
            </small>
          </span>
        </label>
      </fieldset>
      <p className="muted">
        Preferences take effect immediately and apply to automated emails sent to {user.email}.
      </p>
    </section>
  );
}

export function AppSettings() {
  const { user } = useShop();

  return (
    <div className="app-settings-stack">
      <details className="settings-section" open>
        <summary>Appearance <span>Theme and display preferences</span></summary>
        <AppearanceSettings />
      </details>
      <details className="settings-section">
        <summary>Browser alerts <span>Push notifications on this device</span></summary>
        <BrowserAlertSettings />
      </details>
      {user && (
        <details className="settings-section">
          <summary>Email preferences <span>Recommendations and promotions</span></summary>
          <EmailPreferencesSettings />
        </details>
      )}
    </div>
  );
}

type BrowserAlertStatus = 'checking' | 'ready' | 'enabled' | 'blocked' | 'unsupported' | 'unavailable';

export function BrowserAlertSettings() {
  const { user, notify } = useShop();
  const [status, setStatus] = useState<BrowserAlertStatus>('checking');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkSupport(): Promise<void> {
      if (!user) {
        setStatus('ready');
        return;
      }
      if (!('Notification' in window)) {
        setStatus('unsupported');
        return;
      }
      if (Notification.permission === 'denied') {
        setStatus('blocked');
        return;
      }

      try {
        const messaging = await getFirebaseMessaging();
        if (!active) return;
        if (!messaging) {
          setStatus('unsupported');
          return;
        }
        const storedToken = localStorage.getItem('proace-fcm-token');
        const storedOwner = localStorage.getItem('proace-fcm-owner');
        if (
          Notification.permission === 'granted'
          && storedToken
          && storedOwner === String(user.id)
        ) {
          try {
            const dbStatus = await fetchPushDeviceStatus(storedToken);
            if (!active) return;
            if (dbStatus.registered) {
              setStatus('enabled');
              return;
            } else {
              // Token was removed/expired in the database; clean up stale local storage
              localStorage.removeItem('proace-fcm-token');
              localStorage.removeItem('proace-fcm-owner');
              setStatus('ready');
              return;
            }
          } catch {
            // Transient network error: fall back to local token state
            if (active) setStatus('enabled');
            return;
          }
        }
        setStatus('ready');
      } catch {
        if (active) setStatus('unavailable');
      }
    }

    void checkSupport();
    window.addEventListener('storage', checkSupport);
    window.addEventListener(pushDeviceChangeEvent, checkSupport);
    return () => {
      active = false;
      window.removeEventListener('storage', checkSupport);
      window.removeEventListener(pushDeviceChangeEvent, checkSupport);
    };
  }, [user?.id]);

  async function toggleAlerts(): Promise<void> {
    if (!user) return;
    setBusy(true);
    try {
      if (status === 'enabled') {
        await unregisterPushDevice();
        setStatus('ready');
        notify('Browser alerts turned off for this device.');
      } else {
        await registerPushDevice(user.id);
        setStatus('enabled');
        notify('Browser alerts enabled for this device.');
      }
    } catch (error) {
      notify((error as Error).message, true);
      if ('Notification' in window && Notification.permission === 'denied') {
        setStatus('blocked');
      } else {
        setStatus('unavailable');
      }
    } finally {
      setBusy(false);
    }
  }

  const statusCopy: Record<BrowserAlertStatus, string> = {
    checking: 'Checking whether this browser supports alerts…',
    ready: 'Enable alerts to receive account notifications when ProAce is not open.',
    enabled: 'Browser alerts are enabled for your account on this device.',
    blocked: 'Browser permission is blocked. Allow notifications for this site in your browser settings, then reload.',
    unsupported: 'This browser or device does not support push alerts for ProAce.',
    unavailable: 'Could not check browser alert support. You can retry setup here.',
  };
  let StatusIcon = Bell;
  if (status === 'enabled') StatusIcon = CheckCircle2;
  if (status === 'blocked' || status === 'unsupported') StatusIcon = BellOff;
  if (status === 'unavailable') StatusIcon = CircleAlert;

  return (
    <section className="appearance-settings browser-alert-settings" aria-label="Browser alert settings">
      <h2>Browser notifications</h2>
      {!user ? (
        <>
          <p>Sign in to connect this browser to your account’s notifications.</p>
          <Link className="text-link" href="/login?next=/settings">Sign in to enable alerts</Link>
        </>
      ) : (
        <>
          <div className={`browser-alert-status ${status}`} role="status">
            <StatusIcon size={18} aria-hidden="true" />
            <p>{statusCopy[status]}</p>
          </div>
          <button
            type="button"
            className="button browser-alert-toggle"
            disabled={busy || status === 'checking' || status === 'blocked' || status === 'unsupported'}
            aria-pressed={status === 'enabled'}
            onClick={() => void toggleAlerts()}
          >
            {busy ? 'Updating alerts…' : status === 'enabled' ? 'Turn off browser alerts' : 'Enable browser alerts'}
          </button>
        </>
      )}
    </section>
  );
}
