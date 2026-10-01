const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? '',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? '',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
  vapidKey: process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY ?? '',
};

export const dynamic = 'force-dynamic';

export async function GET() {
  const available = Object.values(config).every(Boolean);
  return Response.json(
    { available, ...config },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
