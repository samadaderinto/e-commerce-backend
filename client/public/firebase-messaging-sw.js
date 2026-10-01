importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js');

let messagingPromise;

function getMessaging() {
  if (!messagingPromise) {
    messagingPromise = (async () => {
      const response = await fetch('/api/firebase-config', { cache: 'no-store' });
      if (!response.ok) throw new Error('Unable to load Firebase web configuration.');
      const config = await response.json();
      if (!config.available) return null;

      const firebaseConfig = {
        apiKey: config.apiKey,
        authDomain: config.authDomain,
        projectId: config.projectId,
        storageBucket: config.storageBucket,
        messagingSenderId: config.messagingSenderId,
        appId: config.appId,
      };
      const app = firebase.apps.length
        ? firebase.app()
        : firebase.initializeApp(firebaseConfig);
      return firebase.messaging(app);
    })();
  }
  return messagingPromise;
}

getMessaging().then(instance => {
  if (!instance) return;
  instance.onBackgroundMessage(async payload => {
    const response = await fetch('/api/me', { cache: 'no-store' });
    if (!response.ok) return;
    const user = await response.json();
    if (payload.data?.recipient_id !== String(user.id)) return;

    await self.registration.showNotification(payload.data.title || 'Proace', {
      body: payload.data.body || 'You have a new notification.',
      data: { url: payload.data.url || '/' },
    });
  });
}).catch(error => {
  console.error('Unable to initialize Firebase background messaging.', error);
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const destination = new URL(event.notification.data?.url || '/', self.location.origin);
  if (destination.origin !== self.location.origin) return;
  event.waitUntil(clients.openWindow(destination.href));
});
