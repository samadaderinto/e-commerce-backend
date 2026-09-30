import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
import './globals.css';

export const metadata: Metadata = { title: { default: 'Proace — Your everyday marketplace', template: '%s | Proace' }, description: 'Discover considered essentials, everyday finds and independent sellers. Shop fashion, electronics and more at Proace.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
