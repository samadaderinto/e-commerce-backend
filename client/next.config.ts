import path from 'path';
import type { NextConfig } from 'next';

const isDocker = process.env.DOCKER_BUILD === 'true' || process.env.STANDALONE === 'true';

const config: NextConfig = {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  ...(isDocker ? {
    output: 'standalone',
    outputFileTracingRoot: path.join(__dirname, '../'),
  } : {}),
  typescript: {
    // Dedicated type checking runs via `npm run typecheck` / `tsc --noEmit`
    ignoreBuildErrors: true,
  },
  async headers() {
    return [{ source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
    ] }];
  },
};
export default config;
