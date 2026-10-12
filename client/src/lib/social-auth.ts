export type SocialProvider = 'google' | 'apple';

type GoogleCredentialResponse = {
  credential?: string;
  select_by?: string;
};

type GooglePromptMomentNotification = {
  isNotDisplayed: () => boolean;
  isSkippedMoment: () => boolean;
  getNotDisplayedReason?: () => string;
  getSkippedReason?: () => string;
};

type GoogleIdApi = {
  initialize: (config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }) => void;
  prompt: (callback?: (notification: GooglePromptMomentNotification) => void) => void;
};

type AppleAuthResponse = {
  authorization?: {
    id_token?: string;
  };
  user?: {
    name?: {
      firstName?: string;
      lastName?: string;
    };
  };
};

type AppleIdApi = {
  auth: {
    init: (config: {
      clientId: string;
      scope: string;
      redirectURI: string;
      usePopup: boolean;
    }) => void;
    signIn: () => Promise<AppleAuthResponse>;
  };
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: GoogleIdApi;
      };
    };
    AppleID?: AppleIdApi;
  }
}

const scriptLoads = new Map<string, Promise<void>>();

export function loadSocialScript(src: string, id: string): Promise<void> {
  const existing = scriptLoads.get(id);
  if (existing) return existing;

  const promise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.id = id;
    script.src = src;
    script.async = true;
    script.defer = true;
    const fail = (): void => {
      window.clearTimeout(timeout);
      script.remove();
      scriptLoads.delete(id);
      reject(new Error('Unable to load the sign-in provider. Please try again.'));
    };
    const timeout = window.setTimeout(fail, 15000);
    script.onload = (): void => {
      window.clearTimeout(timeout);
      resolve();
    };
    script.onerror = fail;
    document.head.appendChild(script);
  });
  scriptLoads.set(id, promise);
  return promise;
}

export async function getGoogleCredential(): Promise<{ credential: string }> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
  if (!clientId) {
    throw new Error('Google sign-in is not configured yet.');
  }

  await loadSocialScript('https://accounts.google.com/gsi/client', 'google-identity-services');
  const idApi = window.google?.accounts?.id;
  if (!idApi) {
    throw new Error('Google sign-in is unavailable right now.');
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const fail = (message: string) => {
      if (settled) return;
      settled = true;
      reject(new Error(message));
    };

    const timeout = window.setTimeout(() => {
      fail('Google sign-in timed out. Please try again.');
    }, 60000);

    idApi.initialize({
      client_id: clientId,
      auto_select: false,
      cancel_on_tap_outside: true,
      callback: (response) => {
        if (settled) return;
        window.clearTimeout(timeout);
        if (!response.credential) {
          fail('Google did not return a sign-in credential.');
          return;
        }
        settled = true;
        resolve({ credential: response.credential });
      },
    });

    idApi.prompt((notification) => {
      if (settled) return;
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        window.clearTimeout(timeout);
        fail('Google sign-in was not completed. Please try again or sign in with your email.');
      }
    });
  });
}

export async function getAppleCredential(): Promise<{
  credential: string;
  user?: AppleAuthResponse['user'];
}> {
  const clientId = process.env.NEXT_PUBLIC_APPLE_CLIENT_ID?.trim();
  if (!clientId) {
    throw new Error('Apple sign-in is not configured yet.');
  }

  await loadSocialScript(
    'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js',
    'apple-signin-js'
  );

  const apple = window.AppleID;
  if (!apple) {
    throw new Error('Apple sign-in is unavailable right now.');
  }

  apple.auth.init({
    clientId,
    scope: 'name email',
    redirectURI: window.location.origin,
    usePopup: true,
  });

  const response = await apple.auth.signIn();
  const credential = response.authorization?.id_token;
  if (!credential) {
    throw new Error('Apple did not return a sign-in credential.');
  }

  return {
    credential,
    user: response.user,
  };
}

export async function getSocialCredential(provider: SocialProvider): Promise<{
  credential: string;
  user?: AppleAuthResponse['user'];
}> {
  return provider === 'google' ? getGoogleCredential() : getAppleCredential();
}
