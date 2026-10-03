import path from 'path';
import type { NextConfig } from 'next';

const config: NextConfig = {
  poweredByHeader: false,
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '../'),
  async headers() {
    return [{ source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
    ] }];
  },
};
export default config;
