import type { Metadata } from 'next';
import { Suspense } from 'react';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
import { ErrorMonitor } from '@/components/error-monitor';
import { themeScript } from '@/lib/theme-init';
import './globals.css';
import './admin.css';
import './themes.css';

export const metadata: Metadata = { title: { default: 'ProAce — US marketplace and worldwide digital goods', template: '%s | ProAce' }, description: 'Shop physical products delivered within the United States and digital downloads available worldwide.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head><body><Providers><ErrorMonitor /><Suspense fallback={<main id="main" aria-busy="true" />}><Shell>{children}</Shell></Suspense></Providers></body></html>;
}
