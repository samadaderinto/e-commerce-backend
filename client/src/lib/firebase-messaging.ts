import { getApps, initializeApp } from 'firebase/app';
import { getMessaging, getToken, isSupported, type Messaging } from 'firebase/messaging';
import { api } from '@/lib/api';

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

export async function getFirebaseMessaging(): Promise<Messaging | null> {
  if (typeof window === 'undefined' || !('Notification' in window) || !(await isSupported())) return null;

  const config = await api<FirebaseWebConfig>('firebase-config');
  if (!config.available) return null;

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
  const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  const token = await getToken(messaging, {
    vapidKey: config.vapidKey,
    serviceWorkerRegistration: registration,
  });
  if (!token) throw new Error('Firebase did not return a browser registration token.');

  await api('notifications/devices', 'POST', { token });
  localStorage.setItem(tokenStorageKey, token);
  localStorage.setItem(tokenOwnerStorageKey, String(userId));
}

export async function unregisterPushDevice(): Promise<void> {
  const token = localStorage.getItem(tokenStorageKey);
  if (!token) {
    localStorage.removeItem(tokenOwnerStorageKey);
    return;
  }

  await api('notifications/devices', 'DELETE', { token });
  localStorage.removeItem(tokenStorageKey);
  localStorage.removeItem(tokenOwnerStorageKey);
}
