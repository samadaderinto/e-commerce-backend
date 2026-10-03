import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
import './globals.css';
import './admin.css';

export const metadata: Metadata = { title: { default: 'ProAce — US marketplace and worldwide digital goods', template: '%s | ProAce' }, description: 'Shop physical products delivered within the United States and digital downloads available worldwide.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
