'use client';

import { createContext, ReactNode, useContext, useEffect, useRef, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

type Theme = 'light' | 'dark' | 'system';
type Appearance = 'light' | 'dark';
const normalize = (value: string | null): Theme => value === 'light' || value === 'dark' ? value : 'system';
const scheduledAppearance = (): Appearance => new Date().getHours() >= 6 && new Date().getHours() < 18 ? 'light' : 'dark';
const ThemeContext = createContext<{ preference: Theme; appearance: Appearance; change: (value: Theme) => void; toggle: () => void } | null>(null);

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
    try { preferenceRef.current = normalize(localStorage.getItem('proace-theme')); } catch {}
    setPreference(preferenceRef.current);
    scheduleRef.current = scheduledAppearance();
    apply(preferenceRef.current === 'system' ? scheduleRef.current : preferenceRef.current);
    const checkSchedule = () => {
      // Read the latest saved choice, including changes made while this tab was hidden.
      let saved = preferenceRef.current;
      try { saved = normalize(localStorage.getItem('proace-theme')); } catch {}
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
    try { localStorage.setItem('proace-theme', value); } catch {}
    scheduleRef.current = scheduledAppearance();
    apply(value === 'system' ? scheduleRef.current : value);
  }

  const toggle = () => change(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  return <ThemeContext.Provider value={{ preference, appearance, change, toggle }}>{children}</ThemeContext.Provider>;
}

function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('ThemeProvider missing');
  return context;
}

export function ThemeToggle() {
  const { appearance, toggle } = useTheme();
  const label = appearance === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  return <button type="button" className="icon-button theme-toggle" aria-label={label} title={label} onClick={toggle}>
    {appearance === 'dark' ? <Sun size={21} /> : <Moon size={21} />}
  </button>;
}

export function AppearanceSettings() {
  const { preference, change } = useTheme();
  return <section className="appearance-settings">
    <h2>Default appearance</h2>
    <p>Choose the appearance used throughout the app. Your preference is saved on this browser.</p>
    <fieldset><legend className="sr-only">Default appearance</legend>
      {(['light', 'dark', 'system'] as const).map(value => <label className={`appearance-option ${preference === value ? 'active' : ''}`} key={value}>
        <input type="radio" name="default-appearance" value={value} checked={preference === value} onChange={() => change(value)} />
        <span><strong>{value === 'system' ? 'System' : value === 'light' ? 'Light' : 'Dark'}</strong><small>{value === 'system' ? 'Light 6 a.m.–6 p.m.; dark 6 p.m.–6 a.m., in your local time.' : `Always start in ${value} mode.`}</small></span>
      </label>)}
    </fieldset>
    <p className="muted">The header icon saves your light or dark choice too. Changes apply across all tabs in this browser.</p>
  </section>;
}
