import type { Messaging } from 'firebase/messaging';
import { api } from '@/lib/api';
import { waitForActiveServiceWorker } from '@/lib/service-worker';

type FirebaseWebConfig = {
  available: boolean;
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
  vapidKey: string;
};

const tokenStorageKey = 'proace-fcm-token';
const tokenOwnerStorageKey = 'proace-fcm-owner';
export const pushDeviceChangeEvent = 'proace:push-device-change';

function announcePushDeviceChange(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(pushDeviceChangeEvent));
  }
}

export async function getFirebaseMessaging(): Promise<Messaging | null> {
  if (typeof window === 'undefined' || !('Notification' in window)) return null;

  const config = await api<FirebaseWebConfig>('firebase-config');
  if (!config.available) return null;

  const [{ getApps, initializeApp }, { getMessaging, isSupported }] = await Promise.all([
    import('firebase/app'),
    import('firebase/messaging'),
  ]);
  if (!(await isSupported())) return null;

  const firebaseConfig = {
    apiKey: config.apiKey,
    authDomain: config.authDomain,
    projectId: config.projectId,
    storageBucket: config.storageBucket,
    messagingSenderId: config.messagingSenderId,
    appId: config.appId,
  };
  const app = getApps().find(candidate => candidate.name === '[DEFAULT]')
    ?? initializeApp(firebaseConfig);
  return getMessaging(app);
}

export async function registerPushDevice(userId: string | number): Promise<void> {
  const messaging = await getFirebaseMessaging();
  if (!messaging) throw new Error('Browser push notifications are not available on this device.');

  const permission = Notification.permission === 'granted'
    ? 'granted'
    : await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Allow browser notifications to enable push alerts.');

  const config = await api<FirebaseWebConfig>('firebase-config');
  if (!('serviceWorker' in navigator)) {
    throw new Error('This browser cannot run the service worker needed for push alerts.');
  }

  const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js', {
    scope: '/',
  });
  const readyRegistration = await waitForActiveServiceWorker(registration);

  const { getToken } = await import('firebase/messaging');
  const token = await getToken(messaging, {
    vapidKey: config.vapidKey,
    serviceWorkerRegistration: readyRegistration,
  });
  if (!token) throw new Error('Firebase did not return a browser registration token.');

  await api('notifications/devices', 'POST', { token });
  localStorage.setItem(tokenStorageKey, token);
  localStorage.setItem(tokenOwnerStorageKey, String(userId));
  announcePushDeviceChange();
}

export async function unregisterPushDevice(): Promise<void> {
  const token = localStorage.getItem(tokenStorageKey);
  if (!token) {
    localStorage.removeItem(tokenOwnerStorageKey);
    announcePushDeviceChange();
    return;
  }

  await api('notifications/devices', 'DELETE', { token });
  localStorage.removeItem(tokenStorageKey);
  localStorage.removeItem(tokenOwnerStorageKey);
  announcePushDeviceChange();
}
