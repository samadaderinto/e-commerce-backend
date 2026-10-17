import path from 'path';
import type { NextConfig } from 'next';
import { URL } from 'url';

const isDocker = process.env.DOCKER_BUILD === 'true' || process.env.STANDALONE === 'true';
const mediaUrl = process.env.MINIO_PUBLIC_URL || 'http://127.0.0.1:9000';
const mediaHost = new URL(mediaUrl);
const mediaPath = `/${process.env.MINIO_BUCKET_NAME || 'commerce-images'}/media/**`;
const optimizedImageHosts = Array.from(new Set([
  mediaHost.hostname,
  'minio',
  'images.unsplash.com',
  '*.googleusercontent.com',
]));

const config: NextConfig = {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  ...(isDocker ? {
    output: 'standalone',
    outputFileTracingRoot: path.join(__dirname, '../'),
    outputFileTracingExcludes: {
      '*': [
        'node_modules/@playwright/**',
        'node_modules/playwright/**',
        'node_modules/@types/**',
        'node_modules/typescript/**',
      ],
    },
  } : {}),
  typescript: {
    // Dedicated type checking runs via `npm run typecheck` / `tsc --noEmit`
    ignoreBuildErrors: true,
  },
  env: {
    NEXT_PUBLIC_OPTIMIZED_IMAGE_HOSTS: JSON.stringify(optimizedImageHosts),
    NEXT_PUBLIC_IMAGE_OPTIMIZER_MINIO_URL: isDocker ? 'http://minio:9000' : '',
    NEXT_PUBLIC_MEDIA_ORIGIN: mediaUrl,
  },
  images: {
    remotePatterns: [
      {
        protocol: mediaHost.protocol.replace(':', '') as 'http' | 'https',
        hostname: mediaHost.hostname,
        ...(mediaHost.port ? { port: mediaHost.port } : {}),
        pathname: mediaPath,
      },
      { protocol: 'http', hostname: 'minio', port: '9000', pathname: mediaPath },
      { protocol: 'https', hostname: 'images.unsplash.com', pathname: '/**' },
      { protocol: 'https', hostname: '*.googleusercontent.com', pathname: '/**' },
    ],
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 604800,
    qualities: [60, 65, 70, 75],
    dangerouslyAllowLocalIP: true,
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
