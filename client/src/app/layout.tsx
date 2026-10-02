import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
import './globals.css';
import './admin.css';

export const metadata: Metadata = { title: { default: 'ProAce — International marketplace', template: '%s | ProAce' }, description: 'Shop products and digital goods from independent sellers around the world with ProAce International Consulting and Conglomerate.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
