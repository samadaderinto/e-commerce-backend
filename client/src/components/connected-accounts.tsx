'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { User } from '@/lib/types';
import { getAppleCredential, renderGoogleSignInButton, type SocialCredential } from '@/lib/social-auth';
import { useShop } from './providers';
import { Field } from './ui';

type Provider = 'google' | 'apple';
type ConnectedAccount = { provider: Provider; email: string; connected: boolean };
type AuthenticationMethods = {
  has_password: boolean;
  can_link: boolean;
  accounts: ConnectedAccount[];
};

function GoogleConfirmation({
  onCredential,
  onError,
  disabled,
}: {
  onCredential: (credential: SocialCredential) => void;
  onError: (message: string) => void;
  disabled: boolean;
}): React.ReactNode {
  const target = useRef<HTMLDivElement>(null);
  const handlers = useRef({ onCredential, onError });
  handlers.current = { onCredential, onError };
  useEffect(() => {
    if (!target.current) return;
    let mounted = true;
    void renderGoogleSignInButton(
      target.current,
      'signin_with',
      credential => {
        if (mounted) handlers.current.onCredential({ credential });
      },
      error => {
        if (mounted) handlers.current.onError(error.message);
      },
    ).catch((error: unknown) => {
      if (mounted) handlers.current.onError(error instanceof Error ? error.message : 'Google is unavailable.');
    });
    return () => { mounted = false; };
  }, []);
  return (
    <div
      ref={target}
      className={`google-signin-button${disabled ? ' is-disabled' : ''}`}
      aria-disabled={disabled}
      style={{ pointerEvents: disabled ? 'none' : undefined }}
    />
  );
}

export function ConnectedAccounts(): React.ReactNode {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [action, setAction] = useState<'connect' | 'password'>('connect');
  const [provider, setProvider] = useState<Provider | null>(null);
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const methods = useQuery({
    queryKey: ['auth-methods', user?.id],
    queryFn: () => api<AuthenticationMethods>('auth/methods'),
    enabled: !!user,
    retry: false,
  });
  if (!user) return null;

  function begin(nextProvider: Provider, nextAction: 'connect' | 'password'): void {
    setProvider(nextProvider);
    setAction(nextAction);
    setError('');
    setPassword('');
    setConfirmation('');
    setCurrentPassword('');
  }

  async function confirm(credential: SocialCredential): Promise<void> {
    if (!provider || busy) return;
    if (action === 'password' && (password.length < 8 || password !== confirmation)) {
      setError('Enter a password of at least 8 characters and match its confirmation.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (action === 'password') {
        const response = await api<{ user: User }>('auth/password', 'POST', {
          ...credential, provider, password,
        });
        client.setQueryData<User>(['me'], response.user);
      } else {
        const response = await api<AuthenticationMethods>(`auth/connect/${provider}`, 'POST', {
          ...credential, current_password: currentPassword,
        });
        client.setQueryData(['auth-methods', user?.id], response);
      }
      await client.invalidateQueries({ queryKey: ['auth-methods'] });
      await client.invalidateQueries({ queryKey: ['me'] });
      setProvider(null);
      setCurrentPassword('');
      setPassword('');
      setConfirmation('');
      notify(action === 'password' ? 'Password sign-in is now enabled.' : 'Account connected.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update sign-in methods. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function disconnect(value: Provider): Promise<void> {
    if (!window.confirm(`Disconnect ${value === 'google' ? 'Google' : 'Apple'} sign-in?`)) return;
    setBusy(true);
    setError('');
    try {
      const response = await api<AuthenticationMethods>(`auth/disconnect/${value}`, 'POST', {});
      client.setQueryData(['auth-methods', user?.id], response);
      notify('Account disconnected.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to disconnect this account.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="form-stack" aria-labelledby="connected-accounts-title">
      <h2 id="connected-accounts-title">Sign-in methods</h2>
      {methods.isLoading ? <p>Loading sign-in methods…</p> : methods.error ? (
        <p className="form-error" role="alert">{methods.error.message}</p>
      ) : methods.data ? (
        <>
          <div className="form-stack">
            <strong>Email and password</strong>
            <p className="muted">{methods.data.has_password ? `Connected · ${user.email}` : 'No password set'}</p>
            {methods.data.has_password ? (
              <Link href="/account/profile" className="text-link">Change password in your profile</Link>
            ) : methods.data.can_link ? (
              <div className="form-row">
                {(['google', 'apple'] as const).map(value => (
                  <button key={value} className="button ghost" disabled={busy} onClick={() => begin(value, 'password')}>
                    Set password with {value === 'google' ? 'Google' : 'Apple'} confirmation
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {methods.data.can_link ? (['google', 'apple'] as const).map(value => {
            const account = methods.data?.accounts.find(row => row.provider === value);
            const canDisconnect = !!methods.data?.has_password || (methods.data?.accounts.length || 0) > 1;
            return (
              <div key={value} className="form-stack">
                <strong>{value === 'google' ? 'Google account' : 'Apple account'}</strong>
                <span className="muted">{account ? `Connected · ${account.email}` : 'Not connected'}</span>
                {account ? (
                  <>
                    <button className="button ghost" disabled={busy || !canDisconnect} onClick={() => void disconnect(value)}>
                      Disconnect
                    </button>
                    {!canDisconnect && <p className="muted">Set a password or connect another provider before disconnecting your only sign-in method.</p>}
                  </>
                ) : (
                  <button className="button ghost" disabled={busy} onClick={() => begin(value, 'connect')}>
                    Connect {value === 'google' ? 'Google' : 'Apple'}
                  </button>
                )}
              </div>
            );
          }) : <p className="muted">Staff and administrator accounts use email and password.</p>}
          {provider && (
            <div className="form-stack">
              <h3>{action === 'password' ? 'Set your password' : `Connect ${provider === 'google' ? 'Google' : 'Apple'}`}</h3>
              {action === 'password' ? (
                <>
                  <Field label="New password">
                    <input type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} minLength={8} maxLength={128} />
                  </Field>
                  <Field label="Confirm password">
                    <input type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} maxLength={128} />
                  </Field>
                  <p className="muted">Confirm your existing provider account to enable password sign-in.</p>
                </>
              ) : (
                <>
                  <p className="muted">Choose the account you want to connect. Connecting a different email requires password confirmation.</p>
                  {methods.data.has_password && (
                    <Field label="Current password (required for a different email)">
                      <input type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} />
                    </Field>
                  )}
                </>
              )}
              {provider === 'google' ? (
                <GoogleConfirmation key={`${action}-${provider}`} onCredential={credential => void confirm(credential)} onError={setError} disabled={busy} />
              ) : (
                <button className="button ghost" disabled={busy} onClick={async () => {
                  setBusy(true);
                  try {
                    await confirm(await getAppleCredential());
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Apple sign-in is unavailable.');
                  } finally {
                    setBusy(false);
                  }
                }}>
                  Continue with Apple
                </button>
              )}
              <button className="text-link" disabled={busy} onClick={() => setProvider(null)}>Cancel</button>
            </div>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
        </>
      ) : null}
    </section>
  );
}

export function ConnectedAccountSettings(): React.ReactNode {
  const { user } = useShop();
  if (!user) return null;
  return (
    <details className="settings-section settings-accounts">
      <summary>Sign-in methods <span>Google, Apple and password</span></summary>
      <ConnectedAccounts />
    </details>
  );
}
