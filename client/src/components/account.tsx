'use client';

import { CollectionCount, CollectionFilters, CollectionPagination, financialFields, useCollectionFilters, useDebouncedValue } from './collection-filters';


import type { Page } from '@/lib/types';
import { validateMilitaryAddress } from '@/lib/geo';

import { ActivityDetails, DateStamp } from './activity';
import { displayDate } from '@/lib/datetime';
import { OrderStatusTracker } from './order-status-tracker';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Bell, ChartNoAxesCombined, Check, Clock, ChevronRight, ExternalLink, Eye, EyeOff, FileText, Printer, Heart, Landmark, LockKeyhole, LogOut, MapPin, Package, Pencil, Plus, RotateCcw, ShoppingBag, Settings, Store, Trash2, Truck, UserRound, UsersRound, WalletCards, X } from 'lucide-react';

import { api, ApiError, money } from '@/lib/api';
import { clearSignedInSession } from '@/lib/session-cache';
import type { Address, Order, User, UserWallet } from '@/lib/types';
import {
  getAppleCredential,
  renderGoogleSignInButton,
  type SocialCredential,
} from '@/lib/social-auth';
import { UserAvatarUpload } from './user-avatar';
import { ResponsiveMediaImage } from './ui';
import { ConnectedAccounts } from './connected-accounts';
import { BankAccounts } from './bank-accounts';
import { StripePayoutDestinations } from './stripe-destinations';
import {
  COUNTRIES,
  DEFAULT_COUNTRY_NAME,
  getSubdivisionsForCountry,
  resolveCountry,
  resolveSubdivision,
  validatePostalCode,
  parseAddressLines,
  composeAddress,
  validateStreetAddress,
  validateCity,
  validateUnit,
} from '@/lib/geo';
import { useShop } from './providers';
import { Empty, ErrorState, Field, Loading, ProductImage, Status, useDialogFocus } from './ui';

export function Gate({ children, next = '/account', redirectToSignIn = false }: {
  children: ReactNode;
  next?: string;
  redirectToSignIn?: boolean;
}): React.JSX.Element {
  const router = useRouter();
  const { user, sessionLoading } = useShop();
  useEffect(() => {
    if (redirectToSignIn && !sessionLoading && !user) {
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [redirectToSignIn, sessionLoading, user, next, router]);
  if (redirectToSignIn && !user) return <Loading />;
  if (sessionLoading) return <Loading />;
  if (!user) {
    return (
      <Empty
        title="Make yourself at home"
        text="Sign in to keep your orders, addresses and good finds together."
        href={`/login?next=${encodeURIComponent(next)}`}
        label="Sign in"
        icon={<UserRound size={38} />}
      />
    );
  }
  return <>{children}</>;
}

function AppleIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.38c.62-.75 1.04-1.8 0.93-2.85-.9.04-1.99.6-2.64 1.35-.56.65-1.06 1.7-0.93 2.71 1.01.08 2.02-.46 2.64-1.21z" />
    </svg>
  );
}

function GoogleSignInButton({
  text,
  disabled,
  onCredential,
  onError,
}: {
  text: 'signin_with' | 'signup_with';
  disabled: boolean;
  onCredential: (credential: string) => void;
  onError: (error: Error) => void;
}) {
  const targetRef = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onCredentialRef.current = onCredential;
    onErrorRef.current = onError;
  }, [onCredential, onError]);

  useEffect(() => {
    const target = targetRef.current;
    if (!target) return;

    let mounted = true;
    void renderGoogleSignInButton(
      target,
      text,
      credential => {
        if (mounted) onCredentialRef.current(credential);
      },
      error => {
        if (mounted) onErrorRef.current(error);
      },
    ).catch(error => {
      if (mounted) {
        onErrorRef.current(
          error instanceof Error
            ? error
            : new Error('Google sign-in is unavailable right now.'),
        );
      }
    });

    return () => {
      mounted = false;
      target.replaceChildren();
    };
  }, [text]);

  return (
    <div
      ref={targetRef}
      className={`google-signin-button${disabled ? ' is-disabled' : ''}`}
      aria-disabled={disabled}
    />
  );
}

export function AuthPage({ mode }: { mode: string }) {
  const { login, socialLogin, logout, user, sessionLoading, notify } = useShop();
  const router = useRouter();
  const params = useSearchParams();
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [needsPhone, setNeedsPhone] = useState(false);
  const queryClient = useQueryClient();
  const isRegister = mode === 'register';
  const isForgot = mode === 'forgot-password';
  const isReset = mode === 'reset-password';
  const authBlocked = !isForgot && !isReset && (!!user || sessionLoading);

  useEffect(() => {
    const refParam = params.get('ref');
    if (refParam && typeof window !== 'undefined') {
      try {
        sessionStorage.setItem('proace_referral', refParam);
      } catch {
        /* Ignore storage errors */
      }
    }
  }, [params]);

  const verify = useQuery({
    queryKey: ['verify', params.get('token')],
    queryFn: () =>
      api<{ detail: string }>('auth/verify', 'POST', { token: params.get('token') }),
    enabled: mode === 'verify-email',
    retry: false,
    staleTime: Infinity,
  });

  async function completeSocialLogin(
    provider: 'google' | 'apple',
    socialCredential: SocialCredential,
  ) {
    if (authBlocked) {
      setError('Sign out before signing in with another account.');
      return;
    }
    setBusy(true);
    setError('');
    let storedRef = '';
    if (typeof window !== 'undefined') {
      try {
        storedRef = sessionStorage.getItem('proace_referral') || '';
      } catch {
        /* Continue without a stored referral when browser storage is unavailable. */
      }
    }
    const referralInput = document.querySelector<HTMLInputElement>('input[name="referral_code"]');
    const referralCode = (referralInput?.value || params.get('ref') || storedRef || '').trim();

    try {
      const signedInUser = await socialLogin(provider, {
        ...socialCredential,
        referral_code: referralCode,
      });

      if (typeof window !== 'undefined') {
        try {
          sessionStorage.removeItem('proace_referral');
        } catch {
          /* Ignore storage errors */
        }
      }

      if (!signedInUser.phone1?.trim()) {
        setNeedsPhone(true);
        return;
      }

      const next = params.get('next') || '/account';
      router.push(
        next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')
          ? next
          : '/account'
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAppleSignIn() {
    try {
      await completeSocialLogin('apple', await getAppleCredential());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Apple sign-in is unavailable right now.');
    }
  }

  function handleGoogleCredential(credential: string) {
    void completeSocialLogin('google', { credential });
  }

  function handleGoogleError(providerError: Error) {
    setError(providerError.message);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (authBlocked) {
      setError('Sign out before signing in or creating another account.');
      return;
    }
    setBusy(true);
    setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;

    try {
      if (isRegister) {
        const result = await api<{ detail: string }>('auth/register', 'POST', {
          ...data,
          referral_code: data.referral_code?.trim() || '',
        });
        setMessage(result.detail);
      } else if (isForgot) {
        const result = await api<{ detail: string }>('auth/forgot', 'POST', data);
        setMessage(result.detail);
      } else if (isReset) {
        const result = await api<{ detail: string }>('auth/reset', 'POST', {
          ...data,
          uid: params.get('uid'),
          token: params.get('token'),
        });
        setMessage(result.detail);
      } else {
        await login(data.email, data.password);
        const next = params.get('next') || '/account';
        router.push(
          next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')
            ? next
            : '/account'
        );
      }
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function completePhone(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError('');
    const data = new FormData(event.currentTarget);
    try {
      const updated = await api<User>('me', 'PATCH', {
        phone1: String(data.get('phone1') || '').trim(),
      });
      queryClient.setQueryData<User>(['me'], updated);
      const next = params.get('next') || '/account';
      router.push(
        next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')
          ? next
          : '/account'
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page container">
      <div className="auth-story">
        <span className="eyebrow">YOUR EVERYDAY, A LITTLE BETTER.</span>
        <h2>
          Good things
          <br />
          start here.
        </h2>
        <p>
          A place for your favourite finds.
          <br />
          And the ones you haven&apos;t found yet.
        </p>
        <div className="auth-photo">
          <ResponsiveMediaImage
            src="https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85"
            alt="A minimal watch on a light background"
            sizes="(max-width: 720px) 100vw, 40vw"
          />
        </div>
        <span className="wordmark">
          proace<span>®</span>
        </span>
      </div>

      <div className="auth-form-wrap">
        {needsPhone ? (
          <>
            <h1>Complete your profile</h1>
            <p>Add your phone number to finish setting up your account.</p>
            <form className="form-stack" onSubmit={completePhone}>
              <Field label="Phone number">
                <input
                  name="phone1"
                  type="tel"
                  autoComplete="tel"
                  placeholder="+1 202 555 0100"
                  required
                />
              </Field>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="button" disabled={busy}>
                {busy ? 'Saving…' : 'Save and continue'}
              </button>
            </form>
          </>
        ) : mode === 'verify-email' ? (
          <>
            <div className="auth-icon">
              <Check />
            </div>
            <h1>Email verification</h1>
            {verify.isLoading ? (
              <Loading />
            ) : verify.error ? (
              <p className="form-error">{verify.error.message}</p>
            ) : (
              <p>{verify.data?.detail}</p>
            )}
            <Link className="button" href="/login">
              Continue to sign in <ArrowRight size={17} />
            </Link>
          </>
        ) : message ? (
          <>
            <div className="auth-icon">
              <Check />
            </div>
            <h1>{isReset ? 'A fresh start' : 'Check your inbox'}</h1>
            <p>{message}</p>
            <Link className="button" href="/login">
              Back to sign in <ArrowRight size={17} />
            </Link>
          </>
        ) : (
          <>
            <span className="eyebrow green">
              {isRegister
                ? 'JOIN THE GOOD FINDS'
                : isForgot || isReset
                  ? 'LET’S GET YOU BACK IN'
                  : 'GOOD TO SEE YOU AGAIN'}
            </span>
            <h1>
              {isRegister
                ? 'Make it yours.'
                : isForgot
                  ? 'Forgot your password?'
                  : isReset
                    ? 'Set a new password'
                    : 'Welcome back.'}
            </h1>
            <p>
              {isRegister
                ? 'Create an account for a little more ProAce.'
                : isForgot
                  ? 'We’ll send a reset link to your email address.'
                  : isReset
                    ? 'Choose a strong password for your account.'
                    : 'Sign in to your everyday marketplace.'}
            </p>

            {user && !isForgot && !isReset && (
              <div className="signed-in-notice" role="status">
                <p>You are signed in as {user.email}. Sign out to use another account.</p>
                <div className="form-row">
                  <Link className="text-link" href="/account">Go to your account</Link>
                  <button
                    type="button"
                    className="text-link"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      setError('');
                      try {
                        await logout();
                      } catch (err) {
                        setError((err as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Sign out to switch accounts
                  </button>
                </div>
              </div>
            )}

            {isRegister && params.get('invite') && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: 'rgba(68, 207, 156, 0.12)',
                  border: '1px solid rgba(68, 207, 156, 0.3)',
                  color: 'var(--ink)',
                  fontSize: '0.85rem',
                  lineHeight: 1.4,
                  marginBottom: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <span>🎉</span>
                <span>You&apos;ve been invited to join a store team! Create your account to automatically accept the invitation.</span>
              </div>
            )}

            <form onSubmit={submit} className="form-stack">
              <fieldset className="auth-fields" disabled={busy || authBlocked}>
                {isRegister && (
                  <div className="form-row">
                    <Field label="First name">
                      <input name="first_name" required autoComplete="given-name" maxLength={30} />
                    </Field>
                    <Field label="Last name">
                      <input name="last_name" required autoComplete="family-name" maxLength={30} />
                    </Field>
                  </div>
                )}

                {!isReset && (
                  <Field label="Email address">
                    <input
                      name="email"
                      type="email"
                      required
                      autoComplete="email"
                      defaultValue={params.get('email') || ''}
                      placeholder="you@example.com"
                    />
                  </Field>
                )}

                {isRegister && (
                  <Field label="Phone number">
                    <input
                      name="phone1"
                      type="tel"
                      autoComplete="tel"
                      required
                      placeholder="+1 301 325 1550"
                    />
                  </Field>
                )}

                {isRegister && (
                  <Field label="Referral code (optional)">
                    <input
                      name="referral_code"
                      defaultValue={params.get('ref') || ''}
                      maxLength={70}
                      autoComplete="off"
                    />
                  </Field>
                )}

                {!isForgot && (
                  <Field label="Password">
                    <div className="password-input">
                      <input
                        name="password"
                        type={show ? 'text' : 'password'}
                        required
                        minLength={isRegister || isReset ? 8 : 1}
                        maxLength={128}
                        autoComplete={isRegister || isReset ? 'new-password' : 'current-password'}
                        placeholder={isRegister ? 'At least 8 characters' : 'Your password'}
                      />
                      <button
                        type="button"
                        aria-label={show ? 'Hide password' : 'Show password'}
                        onClick={() => setShow(!show)}
                      >
                        {show ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </Field>
                )}

                {!isRegister && !isForgot && !isReset && (
                  <Link href="/forgot-password" className="forgot-link">
                    Forgot password?
                  </Link>
                )}

                {error && (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                )}

                <button className="button" disabled={busy}>
                  {busy
                    ? 'One moment…'
                    : isRegister
                      ? 'Create account'
                      : isForgot
                        ? 'Send reset link'
                        : isReset
                          ? 'Update password'
                          : 'Sign in'}
                  <ArrowRight size={17} />
                </button>
              </fieldset>
            </form>

            {!isForgot && !isReset && (
              <>
                <div className="auth-divider"><span>or continue with</span></div>
                <div className="social-auth-group">
                  <GoogleSignInButton
                    text={isRegister ? 'signup_with' : 'signin_with'}
                    disabled={busy || authBlocked}
                    onCredential={handleGoogleCredential}
                    onError={handleGoogleError}
                  />
                  <button
                    type="button"
                    className="social-auth-btn apple-btn"
                    disabled={busy || authBlocked}
                    onClick={handleAppleSignIn}
                  >
                    <AppleIcon />
                    <span>Apple</span>
                  </button>
                </div>

              </>
            )}


            <p className="auth-switch">
              {isRegister ? 'Already have an account?' : 'New around here?'}{' '}
              <Link href={isRegister ? '/login' : '/register'}>
                {isRegister ? 'Sign in' : 'Create an account'}
              </Link>
            </p>

            <p className="fine-print">
              By continuing, you agree to our <Link href="/terms">Terms</Link> and{' '}
              <Link href="/privacy">Privacy Policy</Link>.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export function AddressForm({
  onSaved,
  onCancel,
  initialData,
  embedded = false,
}: {
  onSaved: (address: Address) => void;
  onCancel?: () => void;
  initialData?: Address | null;
  embedded?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const client = useQueryClient();
  const isEditing = !!initialData?.id;

  const parsed = parseAddressLines(initialData?.address);
  const [streetAddress, setStreetAddress] = useState(parsed.street);
  const [streetError, setStreetError] = useState('');
  const [touchedStreet, setTouchedStreet] = useState(false);

  const [unitNumber, setUnitNumber] = useState(parsed.unit);
  const [unitError, setUnitError] = useState('');

  const [cityName, setCityName] = useState(initialData?.city || '');
  const [cityError, setCityError] = useState('');
  const [touchedCity, setTouchedCity] = useState(false);

  const initialCountry = resolveCountry(initialData?.country);
  const [selectedCountryName, setSelectedCountryName] = useState(
    initialCountry.name || DEFAULT_COUNTRY_NAME,
  );

  const activeCountry = resolveCountry(selectedCountryName);
  const subdivisions = getSubdivisionsForCountry(activeCountry.code);

  const initialSubdivision = resolveSubdivision(
    initialData?.state,
    activeCountry.code,
  );
  const [selectedState, setSelectedState] = useState(
    initialSubdivision?.name || initialData?.state || (subdivisions[0]?.name ?? ''),
  );

  const [postalCode, setPostalCode] = useState(initialData?.zip || '');
  const [postalError, setPostalError] = useState('');
  const [touchedPostal, setTouchedPostal] = useState(false);

  function handleCountryChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const nextCountryName = e.target.value;
    setSelectedCountryName(nextCountryName);
    const resolved = resolveCountry(nextCountryName);
    const nextSubdivisions = getSubdivisionsForCountry(resolved.code);
    setSelectedState(nextSubdivisions[0]?.name || '');
    if (touchedPostal && postalCode) {
      const res = validatePostalCode(postalCode, resolved.code);
      setPostalError(res.valid ? '' : (res.error || ''));
    }
  }

  function handleStreetChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setStreetAddress(val);
    if (touchedStreet) {
      const res = validateStreetAddress(val);
      setStreetError(res.valid ? '' : (res.error || ''));
    }
  }

  function handleStreetBlur() {
    setTouchedStreet(true);
    const res = validateStreetAddress(streetAddress);
    setStreetError(res.valid ? '' : (res.error || ''));
  }

  function handleUnitChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setUnitNumber(val);
    const res = validateUnit(val);
    setUnitError(res.valid ? '' : (res.error || ''));
  }

  function handleCityChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setCityName(val);
    if (touchedCity) {
      const res = validateCity(val);
      setCityError(res.valid ? '' : (res.error || ''));
    }
  }

  function handleCityBlur() {
    setTouchedCity(true);
    const res = validateCity(cityName);
    setCityError(res.valid ? '' : (res.error || ''));
  }

  function handlePostalChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setPostalCode(val);
    if (touchedPostal) {
      const res = validatePostalCode(val, activeCountry.code);
      setPostalError(res.valid ? '' : (res.error || ''));
    }
  }

  function handlePostalBlur() {
    setTouchedPostal(true);
    const res = validatePostalCode(postalCode, activeCountry.code);
    setPostalError(res.valid ? '' : (res.error || ''));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    const streetCheck = validateStreetAddress(streetAddress);
    if (!streetCheck.valid) {
      setTouchedStreet(true);
      setStreetError(streetCheck.error || 'Please enter a valid street address.');
      return;
    }

    const unitCheck = validateUnit(unitNumber);
    if (!unitCheck.valid) {
      setUnitError(unitCheck.error || 'Please check unit / apartment number.');
      return;
    }

    const cityCheck = validateCity(cityName);
    if (!cityCheck.valid) {
      setTouchedCity(true);
      setCityError(cityCheck.error || 'Please enter a valid city name.');
      return;
    }

    const postalCheck = validatePostalCode(postalCode, activeCountry.code);
    if (!postalCheck.valid) {
      setTouchedPostal(true);
      setPostalError(postalCheck.error || 'Please enter a valid postal code.');
      return;
    }

    if (subdivisions.length > 0 && !selectedState) {
      setError('Please select a state or territory.');
      return;
    }

    setBusy(true);
    const formData = new FormData(event.currentTarget);
    const rawData = Object.fromEntries(formData);
    const fullAddress = composeAddress(streetCheck.formatted, unitCheck.formatted);

    const payload = {
      address: fullAddress,
      city: cityCheck.formatted,
      state: selectedState || (rawData.state as string) || '',
      country: selectedCountryName,
      zip: postalCheck.formatted,
      is_default: rawData.is_default === 'on',
    };

    const militaryError = validateMilitaryAddress(payload);
    if (militaryError) { setError(militaryError); setBusy(false); return; }

    try {
      const address = isEditing
        ? await api<Address>(`addresses/${initialData.id}`, 'PATCH', payload)
        : await api<Address>('addresses', 'POST', payload);
      await client.invalidateQueries({ queryKey: ['addresses'] });
      await client.invalidateQueries({ queryKey: ['shipping-rates'] });
      onSaved(address);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={`form-stack address-form${embedded ? ' address-form-embedded' : ''}`} onSubmit={submit}>
      {!embedded && <h3>{isEditing ? 'Edit delivery address' : 'Add a delivery address'}</h3>}

      {/* Row 1: Country Dropdown (Full Width) */}
      <div className="address-form-country-row">
        <Field label="Country / Destination">
          <select
            name="country"
            value={selectedCountryName}
            onChange={handleCountryChange}
            autoComplete="country-name"
            required
            aria-label="Country or Destination"
          >
            <optgroup label="Active Shipping Destinations">
              {COUNTRIES.filter((c) => c.isSupported).map((c) => (
                <option key={c.code} value={c.name}>
                  {c.name} ({c.code})
                </option>
              ))}
            </optgroup>
            <optgroup label="International Destinations (Currently Unavailable)">
              {COUNTRIES.filter((c) => !c.isSupported).map((c) => (
                <option
                  key={c.code}
                  value={c.name}
                  disabled
                  title="International delivery is currently unavailable in this release"
                >
                  {c.name} ({c.code}) — Coming soon
                </option>
              ))}
            </optgroup>
          </select>
        </Field>
      </div>

      {/* Row 2: Street Address (approx 65%) + Apartment / Unit (approx 35%) */}
      <div className="address-form-street-row">
        <Field label="Street address">
          <input
            name="street"
            value={streetAddress}
            onChange={handleStreetChange}
            onBlur={handleStreetBlur}
            autoComplete="address-line1"
            required
            minLength={5}
            placeholder="Street name and number"
            aria-invalid={!!streetError}
            aria-describedby={streetError ? 'street-address-error' : undefined}
          />
          {streetError && (
            <span id="street-address-error" className="address-field-error" role="alert">
              {streetError}
            </span>
          )}
        </Field>

        <Field label="Unit (optional)">
          <input
            name="unit"
            value={unitNumber}
            onChange={handleUnitChange}
            autoComplete="address-line2"
            maxLength={30}
            placeholder="Apartment or suite"
            aria-invalid={!!unitError}
            aria-describedby={unitError ? 'unit-number-error' : undefined}
          />
          {unitError && (
            <span id="unit-number-error" className="address-field-error" role="alert">
              {unitError}
            </span>
          )}
        </Field>
      </div>

      {/* Row 3: City + State Dropdown + Postal / ZIP Code */}
      <div className="address-form-grid">
        <Field label="City">
          <input
            name="city"
            value={cityName}
            onChange={handleCityChange}
            onBlur={handleCityBlur}
            autoComplete="address-level2"
            required
            placeholder="e.g. Springfield"
            aria-invalid={!!cityError}
            aria-describedby={cityError ? 'city-error' : undefined}
          />
          {cityError && (
            <span id="city-error" className="address-field-error" role="alert">
              {cityError}
            </span>
          )}
        </Field>

        <Field label="State / region">
          {subdivisions.length > 0 ? (
            <select
              name="state"
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                if (error) setError('');
              }}
              autoComplete="address-level1"
              required
              aria-label="State, Province, or Territory"
            >
              <option value="" disabled>
                Select state or territory...
              </option>
              {subdivisions.map((s) => (
                <option key={s.code} value={s.name}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          ) : (
            <input
              name="state"
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              autoComplete="address-level1"
              placeholder="State or Region"
              maxLength={30}
            />
          )}
        </Field>

        <Field label="ZIP / postal code">
          <input
            name="zip"
            type="text"
            inputMode="numeric"
            value={postalCode}
            onChange={handlePostalChange}
            onBlur={handlePostalBlur}
            autoComplete="postal-code"
            required
            maxLength={12}
            placeholder={activeCountry.postalPlaceholder}
            aria-invalid={!!postalError}
            aria-describedby={postalError ? 'postal-code-error' : undefined}
          />
          {postalError && (
            <span id="postal-code-error" className="address-field-error" role="alert">
              {postalError}
            </span>
          )}
        </Field>
      </div>

      <label className="check-row">
        <input
          type="checkbox"
          name="is_default"
          defaultChecked={initialData ? initialData.is_default : true}
        />
        Make this my default address
      </label>
      {error && <p className="form-error">{error}</p>}
      <div className="form-actions">
        <button className="button" disabled={busy}>
          {busy ? 'Saving…' : isEditing ? 'Update address' : 'Save address'}
        </button>
        {onCancel && (
          <button type="button" className="button secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

function WalletTopupModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (url: string) => void }) {
  const [amount, setAmount] = useState('50');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const presets = ['25', '50', '100', '250', '500'];

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const val = Number(amount);
    if (isNaN(val) || val < 5 || val > 5000) {
      setError('Amount must be between $5 and $5,000.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await api<{ url: string }>('wallet/topup-session', 'POST', { amount: val });
      onSuccess(result.url);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="topup-title" style={{ maxWidth: '440px' }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow green">PROACE WALLET</span>
            <h2 id="topup-title">Add Store Funds</h2>
          </div>
          <button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button>
        </div>
        <p className="muted" style={{ fontSize: '13px', margin: '-8px 0 16px' }}>
          Top up your balance instantly using any major payment method. Store balance can be used for 1-click purchases and checkout.
        </p>
        <form className="form-stack" onSubmit={handleSubmit}>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: '8px' }}>
              Quick Select Amount
            </span>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {presets.map(p => (
                <button
                  type="button"
                  key={p}
                  className={`button secondary ${amount === p ? 'active' : ''}`}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '20px',
                    fontSize: '13px',
                    fontWeight: 600,
                    borderColor: amount === p ? 'var(--green)' : 'var(--line)',
                    background: amount === p ? 'var(--green-light)' : 'var(--paper)',
                    color: amount === p ? 'var(--green)' : 'var(--ink)',
                  }}
                  onClick={() => { setAmount(p); setError(''); }}
                >
                  +${p}
                </button>
              ))}
            </div>
          </div>
          <Field label="Custom Amount ($5 – $5,000)">
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <span style={{ position: 'absolute', left: '12px', fontWeight: 600, color: 'var(--muted)' }}>$</span>
              <input
                type="number"
                min="5"
                max="5000"
                step="1"
                required
                value={amount}
                onChange={e => { setAmount(e.target.value); setError(''); }}
                style={{ paddingLeft: '28px', fontSize: '16px', fontWeight: 600 }}
              />
            </div>
          </Field>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions" style={{ marginTop: '16px' }}>
            <button type="button" className="button secondary" onClick={onClose}>Cancel</button>
            <button className="button" disabled={busy}>
              {busy ? 'Redirecting to payment…' : `Continue to Pay $${amount || 0}`}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function PasswordChangeModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (user: User) => void }) {
  const dialogRef = useDialogFocus(true, onClose);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (currentPassword === newPassword) {
      setError('New password must be different from current password.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await api<{ user: User }>('password/change', 'POST', {
        current_password: currentPassword,
        password: newPassword,
      });
      onSuccess(result.user);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section ref={dialogRef} className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="pwd-title" style={{ maxWidth: '440px' }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow green">SECURITY & ACCESS</span>
            <h2 id="pwd-title">Change Password</h2>
          </div>
          <button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button>
        </div>
        <p className="muted" style={{ fontSize: '13px', margin: '-8px 0 16px' }}>
          Update your ProAce password. You will stay signed in on this device.
        </p>
        <form className="form-stack" onSubmit={handleSubmit}>
          <Field label="Current password">
            <div className="password-input">
              <input
                type={showCurrent ? 'text' : 'password'}
                required
                disabled={busy}
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowCurrent(!showCurrent)}
                aria-label={showCurrent ? 'Hide current password' : 'Show current password'}
              >
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          <Field label="New password (min. 8 characters)">
            <div className="password-input">
              <input
                type={showNew ? 'text' : 'password'}
                required
                disabled={busy}
                minLength={8}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowNew(!showNew)}
                aria-label={showNew ? 'Hide new password' : 'Show new password'}
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          <Field label="Confirm new password">
            <div className="password-input">
              <input
                type={showConfirm ? 'text' : 'password'}
                required
                disabled={busy}
                minLength={8}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowConfirm(!showConfirm)}
                aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions" style={{ marginTop: '16px' }}>
            <button type="button" className="button secondary" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="button" disabled={busy}>
              {busy ? 'Updating…' : 'Update password'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function AccountPage({ section = 'overview' }: { section?: string }) {
  const { user, logout, notify } = useShop(); const router = useRouter(); const client = useQueryClient(); const params = useSearchParams();
  const [adding, setAdding] = useState(false); const [editingAddress, setEditingAddress] = useState<Address | null>(null); const [busy, setBusy] = useState(false);
  const [showTopupModal, setShowTopupModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const isBackoffice = Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin);
  const orderFilters = useCollectionFilters();
  const walletFilters = useCollectionFilters();
  const orders = useQuery({
    queryKey: ['orders', user?.id, orderFilters.query],
    queryFn: () => api<Page<Order>>(`orders?paginated=1&${orderFilters.query}`),
    enabled: !!user && !isBackoffice,
    refetchInterval: 15000,
  });
  const addresses = useQuery({ queryKey: ['addresses', user?.id], queryFn: () => api<Address[]>('addresses'), enabled: !!user && !isBackoffice });
  const wallet = useQuery({ queryKey: ['wallet', user?.id, walletFilters.query], queryFn: () => api<UserWallet>(`wallet?${walletFilters.query}`), enabled: !!user && !isBackoffice });
  let walletBalanceLabel: string = 'Loading…';
  if (wallet.error) {
    walletBalanceLabel = 'Unavailable';
  } else if (wallet.data) {
    walletBalanceLabel = money(wallet.data.balance);
  }
  function fundWallet(): void {
    if (wallet.isLoading || wallet.isError) return;
    setShowTopupModal(true);
  }
  useEffect(() => {
    if (isBackoffice && (section === 'overview' || ['orders', 'wallet', 'addresses'].includes(section))) {
      router.replace('/account/profile');
    }
  }, [isBackoffice, section, router]);
  useEffect(() => {
    const sessionId = params.get('topup_session_id');
    if (!sessionId || !user || isBackoffice) return;
    void api<{ detail: string; balance: string }>('wallet/topup-confirm', 'POST', { session_id: sessionId })
      .then(result => { notify(result.detail); void client.invalidateQueries({ queryKey: ['wallet', user.id] }); router.replace('/account/wallet'); })
      .catch(error => notify((error as Error).message, true));
  }, [params, user?.id, isBackoffice]);
  useEffect(() => {
    if (params.get('topup_cancelled') === '1' && user && !isBackoffice) {
      void api<{ detail?: string; released?: boolean }>('wallet/topup-cancel', 'POST', {})
        .then((result) => {
          notify(result.released ? 'Top-up cancelled.' : (result.detail || 'Top-up status could not be confirmed.'), !result.released);
          void client.invalidateQueries({ queryKey: ['wallet', user.id] });
          router.replace('/account/wallet');
        })
        .catch((error: unknown) => {
          notify(error instanceof Error ? error.message : 'Unable to verify top-up cancellation.', true);
          router.replace('/account/wallet');
        });
    }
  }, [params, user?.id, isBackoffice, router, notify, client]);
  const links = isBackoffice
    ? [
        ['profile', 'Personal details', UserRound],
        ['payout-accounts', 'Payout accounts', Landmark],
      ] as const
    : [
        ['overview', 'Overview', UserRound],
        ['orders', 'My orders', Package],
        ['wallet', 'ProAce Wallet', WalletCards],
        ['addresses', 'Address book', MapPin],
        ['payout-accounts', 'Payout accounts', Landmark],
        ['affiliates', 'Affiliates & referrals', UsersRound],
        ['profile', 'Personal details', UserRound],
      ] as const;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const updated = await api<User>('me', 'PATCH', Object.fromEntries(new FormData(event.currentTarget)));
      client.setQueryData(['me'], updated);
      notify('Your details have been updated');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Gate>
      <div className="container account-page">
        <div className="breadcrumb">
          <Link href={isBackoffice ? '/admin' : '/'}>{isBackoffice ? 'Platform dashboard' : 'Home'}</Link>
          <ChevronRight size={12} />
          <span>My account</span>
        </div>
        <div className="account-layout">
          <aside className="account-sidebar">
            <div className="account-avatar">
              {user?.avatar_url ? (
                <ResponsiveMediaImage
                  src={user.avatar_url}
                  alt={user.first_name}
                  style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                  sizes="64px"
                  width={128}
                  height={128}
                />
              ) : (
                user?.first_name?.[0] || 'P'
              )}
            </div>
            <h2>{user?.first_name} {user?.last_name}</h2>
            <p>{user?.email}</p>
            {isBackoffice && (
              <div style={{ marginTop: '0.25rem' }}>
                <span
                  className="account-badge admin"
                  style={{
                    display: 'inline-block',
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontWeight: 600,
                    background: 'var(--green-light, #ecfdf5)',
                    color: 'var(--green, #047857)',
                  }}
                >
                  {user?.is_superuser
                    ? 'Root Administrator'
                    : user?.is_business_admin
                    ? 'Business Administrator'
                    : 'Staff Member'}
                </span>
              </div>
            )}
            <nav>
              {links.map(([key, name, Icon]) => (
                <Link
                  className={section === key || (isBackoffice && section === 'overview') ? 'active' : ''}
                  key={key}
                  href={key === 'overview' ? '/account' : `/account/${key}`}
                >
                  <Icon size={19} />
                  {name}
                </Link>
              ))}
              <Link href="/notifications">
                <Bell size={19} />
                Notifications
              </Link>
              <Link href="/settings">
                <Settings size={19} />
                App settings
              </Link>
              {isBackoffice ? (
                <>
                  <Link href="/admin">
                    <ChartNoAxesCombined size={19} />
                    Platform dashboard
                    <ArrowRight size={15} />
                  </Link>
                  {(user?.is_superuser || user?.is_business_admin) && (
                    <Link href="/admin/staff">
                      <UsersRound size={19} />
                      Manage staff
                      <ArrowRight size={15} />
                    </Link>
                  )}
                  <Link href="/merchant">
                    <Store size={19} />
                    Store operations
                    <ArrowRight size={15} />
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/saved">
                    <Heart size={19} />
                    Saved items
                  </Link>
                  <Link href="/merchant">
                    <Store size={19} />
                    Seller workspace
                    <ArrowRight size={15} />
                  </Link>
                </>
              )}
              <button
                onClick={async () => {
                  try {
                    await logout();
                    router.push('/');
                  } catch (error) {
                    notify((error as Error).message, true);
                  }
                }}
              >
                <LogOut size={19} />
                Sign out
              </button>
            </nav>
          </aside>
          <div className="account-content">
            {section === 'profile' || (isBackoffice && section !== 'payout-accounts') ? (
              <>
                <h1>Personal details</h1>
                <ActivityDetails {...user} />
                <UserAvatarUpload user={user} />
                <p className="muted">A little about you.</p>
                <form className="form-stack profile-form" onSubmit={save}>
                  <div className="form-row">
                    <Field label="First name">
                      <input name="first_name" defaultValue={user?.first_name} required maxLength={30} />
                    </Field>
                    <Field label="Last name">
                      <input name="last_name" defaultValue={user?.last_name} required maxLength={30} />
                    </Field>
                  </div>
                  <Field label="Email address">
                    <input value={user?.email || ''} disabled />
                  </Field>
                  <Field label="Phone number">
                    <input type="tel" name="phone1" defaultValue={user?.phone1} required />
                  </Field>
                  <button className="button" disabled={busy}>
                    {busy ? 'Saving…' : 'Save changes'}
                  </button>
                  <button
                    type="button"
                    className="text-link"
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                    onClick={() => setShowPasswordModal(true)}
                  >
                    <span>Change your password</span>
                    <ArrowRight size={16} />
                  </button>
                </form>
                <ConnectedAccounts />
              </>
            ) : section === 'overview' ? (
              <>
                <span className="eyebrow green">YOUR LITTLE CORNER OF PROACE</span>
                <h1>Hello, {user?.first_name}.</h1>
                <p className="muted">All your good finds, in one place.</p>
                <div className="account-stat-grid">
                  <Link href="/account/orders">
                    <Package />
                    <strong>{orders.data?.count || 0}</strong>
                    <span>Orders</span>
                    <ArrowRight size={17} />
                  </Link>
                  <Link href="/account/wallet">
                    <WalletCards />
                    <strong>{walletBalanceLabel}</strong>
                    <span>Wallet balance</span>
                    <ArrowRight size={17} />
                  </Link>
                  <Link href="/account/addresses">
                    <MapPin />
                    <strong>{addresses.data?.length || 0}</strong>
                    <span>Saved addresses</span>
                    <ArrowRight size={17} />
                  </Link>
                  <Link href="/account/payout-accounts">
                    <Landmark />
                    <strong>Manage</strong>
                    <span>Payout accounts</span>
                    <ArrowRight size={17} />
                  </Link>
                </div>
                <div className="section-heading">
                  <h2>Recent orders</h2>
                  <Link className="text-link" href="/account/orders">
                    View all <ArrowRight size={16} />
                  </Link>
                </div>
                <OrderList
                  orders={orders.data?.results.slice(0, 3)}
                  loading={orders.isLoading}
                  error={orders.error}
                />
              </>
            ) : section === 'payout-accounts' ? (
              <div className="payout-accounts-page">
                <span className="eyebrow green">ACCOUNT FINANCE</span>
                <h1>Payout accounts</h1>
                <p className="muted">
                  Manage saved bank and Stripe destinations for withdrawals.
                </p>
                <BankAccounts heading="Saved bank accounts" />
                <StripePayoutDestinations />
              </div>
            ) : section === 'orders' ? (
              <>
                <h1>My orders</h1>
                <CollectionFilters filters={orderFilters} label="orders" fields={[
                  { key: 'status', label: 'Status', options: ['pending', 'confirmed', 'shipped', 'delivered', 'picked up', 'cancelled', 'refunded'].map(value => ({ value, label: value })) },
                  { key: 'payment_type', label: 'Payment method', options: ['card', 'wallet', 'cash_on_delivery', 'stripe_wallet'].map(value => ({ value, label: value.replaceAll('_', ' ') })) },
                  ...financialFields,
                ]} />
                {typeof orders.data?.count === 'number' && (
                  <CollectionCount count={orders.data.count} />
                )}
                {orderFilters.active && !orders.isLoading && !orders.data?.results.length && (
                  <p className="muted">No orders match your filters. Reset filters to see all orders.</p>
                )}
                <p className="muted">Keep an eye on your latest finds.</p>
                <OrderList
                  orders={orders.data?.results}
                  filtered={orderFilters.active}
                  loading={orders.isLoading}
                  error={orders.error}
                />
                <CollectionPagination filters={orderFilters} count={orders.data?.count || 0} />
              </>
            ) : section === 'wallet' ? (
              <div>
                <span className="eyebrow green">STORE CREDIT & BALANCES</span>
                <h1>ProAce Wallet</h1>
                <p className="muted">
                  Use your available balance for instant 1-click purchases and immediate refund store credit.
                </p>
                <div className="account-stat-grid" style={{ gridTemplateColumns: '1fr' }}>
                  <div className="stat-item stat-0 wallet-stat-card">
                    <div>
                      <span style={{ fontWeight: 600 }}>Available Store Balance</span>
                      <WalletCards size={24} color="var(--green)" />
                    </div>
                    <strong className="wallet-balance-amount" aria-live="polite">{walletBalanceLabel}</strong>
                    <small>Automatically available at checkout to pay for any product.</small>
                  </div>
                </div>
                <div className="section-heading" style={{ marginTop: '2rem' }}>
                  <h2>Recent wallet activity</h2>
                  <button
                    className="button"
                    disabled={wallet.isLoading || wallet.isError}
                    onClick={fundWallet}
                  >
                    Add funds
                  </button>
                </div>
                <CollectionFilters filters={walletFilters} label="wallet transactions" fields={[
                  { key: 'transaction_type', label: 'Type', options: [{ value: 'credit', label: 'Credit' }, { value: 'debit', label: 'Debit' }] },
                  { key: 'source', label: 'Source' },
                  ...financialFields,
                ]} />
                {typeof wallet.data?.count === 'number' && (
                  <CollectionCount count={wallet.data.count} />
                )}
                {wallet.isLoading ? (
                  <Loading />
                ) : wallet.error ? (
                  <ErrorState error={wallet.error} retry={() => wallet.refetch()} />
                ) : !wallet.data?.transactions?.length ? (
                  <Empty
                    title={walletFilters.active ? "No transactions match your filters" : "No transactions yet"}
                    text={walletFilters.active ? "Reset filters to see all transactions." : "When you receive credit or pay with your wallet, activity appears here."}
                  />
                ) : (
                  <>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Created</th>
                            <th>Reference</th>
                            <th>Type</th>
                            <th>Source</th>
                            <th>Description</th>
                            <th>Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {wallet.data.transactions.map((tx) => (
                            <tr key={tx.id}>
                              <td><DateStamp value={tx.created} dateOnly /></td>
                              <td>
                                {tx.reference ? (
                                  <strong style={{ fontFamily: 'var(--mono, monospace)', fontSize: '12px' }}>
                                    {tx.reference}
                                  </strong>
                                ) : (
                                  <span className="muted">—</span>
                                )}
                              </td>
                              <td>
                                <span className={tx.transaction_type === 'credit' ? 'status active' : 'status'}>
                                  {tx.transaction_type.toUpperCase()}
                                </span>
                              </td>
                              <td style={{ textTransform: 'capitalize' }}>{tx.source}</td>
                              <td>{tx.description}</td>
                              <td
                                style={{
                                  fontWeight: 600,
                                  color: tx.transaction_type === 'credit' ? 'var(--green)' : 'var(--ink)',
                                }}
                              >
                                {tx.transaction_type === 'credit' ? `+${money(tx.amount)}` : `-${money(tx.amount)}`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <CollectionPagination filters={walletFilters} count={wallet.data?.count || 0} />
                  </>
                )}
              </div>
            ) : section === 'addresses' ? (
              <>
                <div className="section-heading">
                  <h1>Address book</h1>
                  <button
                    className="button"
                    onClick={() => {
                      setAdding(true);
                      setEditingAddress(null);
                    }}
                  >
                    <Plus size={17} />Add address
                  </button>
                </div>
                {adding && (
                  <AddressForm
                    onSaved={() => {
                      setAdding(false);
                      notify('Address saved');
                    }}
                    onCancel={() => setAdding(false)}
                  />
                )}
                {editingAddress && (
                  <AddressForm
                    initialData={editingAddress}
                    onSaved={() => {
                      setEditingAddress(null);
                      notify('Address updated');
                    }}
                    onCancel={() => setEditingAddress(null)}
                  />
                )}
                {addresses.isLoading ? (
                  <Loading />
                ) : addresses.error ? (
                  <ErrorState error={addresses.error} />
                ) : !addresses.data?.length && !adding && !editingAddress ? (
                  <div className="empty-state">
                    <MapPin size={35} />
                    <h2>Where should we send your finds?</h2>
                    <p>Add your first address to make checkout a little easier.</p>
                  </div>
                ) : (
                  <div className="address-grid">
                    {addresses.data?.map((address) => (
                      <article className="address-card" key={address.id}>
                        <div>
                          <MapPin size={18} />
                          {address.is_default && <span className="status">Default address</span>}
                          <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
                            <button
                              className="icon-button"
                              aria-label={`Edit ${address.address}`}
                              onClick={() => {
                                setEditingAddress(address);
                                setAdding(false);
                              }}
                            >
                              <Pencil size={15} />
                            </button>
                            <button
                              className="icon-button"
                              aria-label={`Delete ${address.address}`}
                              onClick={async () => {
                                try {
                                  await api('addresses', 'DELETE', { id: address.id });
                                  await client.invalidateQueries({ queryKey: ['addresses'] });
                                  notify('Address removed');
                                } catch (error) {
                                  notify((error as Error).message, true);
                                }
                              }}
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                        <strong>{address.address}</strong>
                        <p>
                          {address.city}, {address.state}<br />
                          {address.country}, {address.zip}
                        </p>
                        <div
                          style={{
                            marginTop: '12px',
                            paddingTop: '10px',
                            borderTop: '1px solid var(--line)',
                            display: 'flex',
                            justifyContent: 'flex-end',
                            alignItems: 'center',
                          }}
                        >
                          <Link
                            href={`/checkout?address_id=${address.id}`}
                            className="text-link"
                            style={{ fontSize: '11px', color: 'var(--green)' }}
                          >
                            <span>Use for checkout</span>
                            <ArrowRight size={13} />
                          </Link>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </>
            ) : null}
            {showTopupModal && (
              <WalletTopupModal
                onClose={() => setShowTopupModal(false)}
                onSuccess={(url) => {
                  setShowTopupModal(false);
                  window.location.assign(url);
                }}
              />
            )}
            {showPasswordModal && (
              <PasswordChangeModal
                onClose={() => setShowPasswordModal(false)}
                onSuccess={(updatedUser) => {
                  setShowPasswordModal(false);
                  client.setQueryData(['me'], updatedUser);
                  void client.invalidateQueries({ queryKey: ['me'] });
                  notify('Password updated successfully');
                }}
              />
            )}
          </div>
        </div>
      </div>
    </Gate>
  );
}

function OrderList({ orders, loading, error, filtered = false }: { orders?: Order[]; loading: boolean; error: Error | null; filtered?: boolean }) {
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (!orders?.length) {
    return <Empty title={filtered ? "No orders match your filters" : "Your first find is waiting"} text={filtered ? "Reset filters to see all orders." : "When you place an order, you can follow it right here."} />;
  }
  return (
    <div className="order-list">
      {orders.map((order) => (
        <Link href={`/orders/${order.id}`} className="order-row" key={order.id}>
          <ProductImage src={order.items[0]?.image} alt={order.items[0]?.title || 'Order'} />
          <div>
            <strong>{order.reference}</strong>
            <p>
              {order.items[0]?.title || 'Your order'}
              {order.items.length > 1 ? ` + ${order.items.length - 1} more` : ''}
            </p>
            <small>
              <DateStamp value={order.created} dateOnly />
            </small>
          </div>
          <Status value={order.status} />
          <strong>{money(order.total)}</strong>
          <ChevronRight size={18} />
        </Link>
      ))}
    </div>
  );
}

function carrierTrackingUrl(carrier: string, trackingNumber: string): string {
  const encodedNumber = encodeURIComponent(trackingNumber);
  switch (carrier.toUpperCase()) {
    case 'FEDEX':
      return `https://www.fedex.com/fedextrack/?trknbr=${encodedNumber}`;
    case 'UPS':
      return `https://www.ups.com/track?tracknum=${encodedNumber}`;
    case 'DHL':
      return `https://www.dhl.com/us-en/home/tracking.html?tracking-id=${encodedNumber}`;
    case 'USPS':
      return `https://tools.usps.com/go/TrackConfirmAction?tLabels=${encodedNumber}`;
    default:
      return '';
  }
}

export function OrderPage({ id }: { id: string }) {
  const { user, notify, logout } = useShop();
  const params = useSearchParams();
  const client = useQueryClient();
  const router = useRouter();
  const loginUrl = `/login?next=${encodeURIComponent(`/orders/${id}`)}`;
  const [switchingAccount, setSwitchingAccount] = useState(false);
  const order = useQuery({
    queryKey: ['order', id, user?.id],
    queryFn: () => api<Order>(`orders/${id}`),
    enabled: !!user,
    retry: (attempt, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && attempt < 1,
    refetchInterval: query => query.state.error instanceof ApiError
      && [401, 403, 404].includes(query.state.error.status) ? false : 15000,
  });
  const unauthorized = order.error instanceof ApiError && order.error.status === 401;
  const unavailable = order.error instanceof ApiError && [403, 404].includes(order.error.status);

  useEffect(() => {
    if (!unauthorized) return;
    void clearSignedInSession(client).then(() => router.replace(loginUrl));
  }, [unauthorized, client, router, loginUrl]);

  async function switchAccount(): Promise<void> {
    setSwitchingAccount(true);
    try {
      await logout();
      router.replace(loginUrl);
    } catch {
      notify('Unable to switch accounts. Please try again.', true);
    } finally {
      setSwitchingAccount(false);
    }
  }

  const [requestingRefund, setRequestingRefund] = useState(false);
  const [editingRefund, setEditingRefund] = useState(false);
  const [reason, setReason] = useState('item_damaged');
  const [otherReason, setOtherReason] = useState('');
  const [refundProducts, setRefundProducts] = useState<number[]>([]);
  const [refundType, setRefundType] = useState('store_credit');
  const [busy, setBusy] = useState(false);
  const [viewer, setViewer] = useState<{ url: string; title: string; kind: 'pdf' | 'image' } | null>(null);
  function viewerKind(title: string): 'pdf' | 'image' | null {
    const extension = title.toLowerCase().split('?')[0].split('.').pop();
    if (extension === 'pdf') return 'pdf';
    if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'avif'].includes(extension || '')) return 'image';
    return null;
  }

  const data = order.data;
  const showPlacedMessage: boolean = params.has('placed')
    && ['pending', 'confirmed'].includes(data?.status || '');
  const isAllDigital = data?.items?.every(item => item.is_digital) ?? false;
  const hasPhysical = data?.items?.some(item => !item.is_digital) ?? false;
  const createdTime: number = data ? new Date(data.created).getTime() : 0;
  function isWithinReturnWindow(item: Order['items'][number]): boolean {
    if (item.is_digital) return false;
    const deliveredAt: string | null | undefined = data?.fulfillments?.find(
      fulfillment => fulfillment.store === item.store
    )?.delivered_at || data?.delivered_at;
    return !deliveredAt || Date.now() <= new Date(deliveredAt).getTime() + 7 * 24 * 60 * 60 * 1000;
  }
  const isWithin7Days: boolean = (data?.items || []).some(isWithinReturnWindow);
  const activeRefund = data?.active_refund;
  const isRefundPending = Boolean(activeRefund?.is_pending);
  const isRefundEditable: boolean = isRefundPending && activeRefund?.is_editable !== false;
  const claimedProductIds = data?.claimed_product_ids || [];
  const unclaimedPhysicalItems = (data?.items || []).filter(
    (item) => isWithinReturnWindow(item) && !claimedProductIds.includes(item.product)
  );
  const canRequestRefund: boolean = !isRefundPending
    && hasPhysical
    && isWithin7Days
    && unclaimedPhysicalItems.length > 0
    && Number(data?.paid_total || 0) > Number(data?.refunded_total || 0)
    && !['refunded', 'cancelled'].includes(data?.status || '');

  function openNewRefund() {
    setEditingRefund(false);
    setReason('item_damaged');
    setOtherReason('');
    setRefundType('store_credit');
    setRefundProducts([]);
    setRequestingRefund(true);
  }

  function openEditRefund() {
    if (!activeRefund || !isRefundEditable) return;
    setEditingRefund(true);
    const knownReasons: Record<string, string> = {
      'Item damaged': 'item_damaged',
      'Wrong item received': 'wrong_item_received',
      'Item missing': 'item_missing',
    };
    const mappedReason = knownReasons[activeRefund.reason];
    if (mappedReason) {
      setReason(mappedReason);
      setOtherReason('');
    } else {
      setReason('other');
      setOtherReason(activeRefund.reason);
    }
    setRefundType(activeRefund.refund_type || 'store_credit');
    setRefundProducts(activeRefund.product_ids || []);
    setRequestingRefund(true);
  }

  async function submitRefund(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      if (editingRefund) {
        await api(`orders/${id}/refund`, 'PATCH', {
          reason,
          other_reason: reason === 'other' ? otherReason : '',
          product_ids: refundProducts,
          refund_type: refundType,
        });
        notify('Refund request updated. We will review your return within 1–2 business days.');
      } else {
        await api(`orders/${id}/refund`, 'POST', {
          reason,
          other_reason: reason === 'other' ? otherReason : '',
          product_ids: refundProducts,
          refund_type: refundType,
        });
        notify('Refund request submitted. We will review your return within 1–2 business days.');
      }
      await client.invalidateQueries({ queryKey: ['order', id] });
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['wallet'] });
      setRequestingRefund(false);
      setEditingRefund(false);
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const carrierCode = (data?.carrier || 'USPS').toUpperCase();
  const carrierName =
    carrierCode === 'FEDEX'
      ? 'FedEx'
      : carrierCode === 'UPS'
      ? 'UPS'
      : carrierCode === 'DHL'
      ? 'DHL'
      : carrierCode === 'USPS'
      ? 'USPS'
      : data?.carrier || 'Carrier';
  const carrierDisplay = ['USPS', 'FEDEX', 'UPS', 'DHL'].includes(carrierCode)
    ? `${carrierName}.com`
    : carrierName;
  const trackingUrl =
    data?.tracking_url ||
    (carrierCode === 'FEDEX'
      ? `https://www.fedex.com/fedextrack/?trknbr=${encodeURIComponent(data?.tracking_number || '')}`
      : carrierCode === 'UPS'
      ? `https://www.ups.com/track?tracknum=${encodeURIComponent(data?.tracking_number || '')}`
      : carrierCode === 'DHL'
      ? `https://www.dhl.com/us-en/home/tracking.html?tracking-id=${encodeURIComponent(data?.tracking_number || '')}`
      : `https://tools.usps.com/go/TrackConfirmAction?tLabels=${encodeURIComponent(data?.tracking_number || '')}`);
  const multipleFulfillments = (data?.fulfillments || []).length > 1;

  const hoursElapsed = (Date.now() - createdTime) / (1000 * 60 * 60);
  const isWithin12Hours = hoursElapsed <= 12;
  const hasDigital = data?.items?.some((item) => item.is_digital) ?? false;
  const canCancel: boolean = hasPhysical
    && !hasDigital
    && isWithin12Hours
    && ['pending', 'confirmed'].includes(data?.status || '')
    && (data?.fulfillments || []).every((fulfillment) => fulfillment.status === 'confirmed');
  const paymentMethods: Record<string, string> = {
    user_wallet: 'ProAce Wallet',
    wallet: 'ProAce Wallet',
    stripe_wallet: 'Card & ProAce Wallet',
    card: 'Card',
  };
  const paymentMethod: string = paymentMethods[(data?.payment_type || '').toLowerCase().replaceAll(' ', '_')]
    || data?.payment_type || 'Online payment';
  const paidAmount: number = Number(data?.paid_total || 0);
  const refundedAmount: number = Number(data?.refunded_total || 0);
  function paymentState(): string {
    if (paidAmount <= 0) {
      if (Number(data?.total) === 0) return 'No payment required';
      return data?.status === 'cancelled' ? 'No payment collected' : 'Awaiting payment';
    }
    if (refundedAmount >= paidAmount) return 'Refunded';
    if (refundedAmount > 0) return 'Partially refunded';
    return paidAmount >= Number(data?.total || 0) ? 'Paid' : 'Partially paid';
  }

  const [cancelling, setCancelling] = useState(false);

  async function cancelOrder() {
    if (!window.confirm('Cancel this order? Wallet payments return to your ProAce Wallet, and card payments return to the original payment method.')) {
      return;
    }
    setCancelling(true);
    try {
      await api(`orders/${id}/cancel`, 'POST');
      await client.invalidateQueries({ queryKey: ['order', id] });
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['wallet'] });
      notify('Order cancelled. Any settled payment has been returned to its original payment method.');
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setCancelling(false);
    }
  }

  return (
    <Gate next={`/orders/${id}`} redirectToSignIn>
      <div className="container order-detail">
        <Link className="text-link" href="/account/orders">
          <ArrowLeft size={16} />All orders
        </Link>
        {order.isLoading ? (
          <Loading />
        ) : unauthorized ? (
          <Loading />
        ) : unavailable ? (
          <section className="empty-state" aria-labelledby="order-unavailable-title">
            <LockKeyhole size={38} aria-hidden="true" />
            <h2 id="order-unavailable-title">This order isn’t available to your account</h2>
            <p>Check your orders or switch to the account used for this purchase.</p>
            <div className="form-actions">
              <Link className="button" href="/account/orders">Your orders</Link>
              <button
                type="button"
                className="button secondary"
                disabled={switchingAccount}
                onClick={() => void switchAccount()}
              >
                {switchingAccount ? 'Switching account…' : 'Switch account'}
              </button>
            </div>
          </section>
        ) : order.error ? (
          <ErrorState error={new Error('Unable to load this order right now. Please try again.')} retry={() => void order.refetch()} />
        ) : (
          data && (
            <>
              <div className="order-success">
                <div className={['pending', 'cancelled', 'refunded'].includes(data.status) ? 'order-outcome-icon' : 'success-icon'}>
                  {data.status === 'pending' ? (
                    <Clock size={30} />
                  ) : data.status === 'cancelled' ? (
                    <X size={30} />
                  ) : data.status === 'refunded' ? (
                    <RotateCcw size={30} />
                  ) : (
                    <Check size={30} />
                  )}
                </div>
                <span className="eyebrow green">
                  {showPlacedMessage ? 'A GOOD FIND, INDEED' : 'YOUR ORDER'}
                </span>
                <h1>{showPlacedMessage ? 'It’s on the list.' : data.reference}</h1>
                <p>
                  {showPlacedMessage
                    ? `Your order ${data.reference} is ${data.status}. Thank you for shopping with ProAce.`
                    : `Placed on ${displayDate(data.created)}`}
                </p>
                <div className="order-status-actions">
                  <Status value={data.status} />
                  <button
                    type="button"
                    className="button secondary receipt-print-button"
                    onClick={() => window.print()}
                  >
                    <Printer size={16} />Print receipt
                  </button>
                </div>
              </div>

              {multipleFulfillments ? (
                <div className="shipping-banner shipping-banner-multiple">
                  <div className="shipment-tracking-heading">
                    <Truck size={24} className="shipping-banner-icon" />
                    <strong className="shipping-banner-title">Delivery updates by store</strong>
                  </div>
                  <div className="shipment-tracking-list">
                    {data.fulfillments.map((fulfillment) => {
                      const trackingHref = fulfillment.tracking_number
                        ? carrierTrackingUrl(fulfillment.carrier, fulfillment.tracking_number)
                        : '';
                      return (
                        <div className="shipment-tracking-row" key={fulfillment.store}>
                          <div className="shipment-tracking-meta">
                            <strong>{fulfillment.store_name || `Store ${fulfillment.store}`}</strong>
                            <span>Status: {fulfillment.status.toUpperCase()}</span>
                            {fulfillment.tracking_number && (
                              <span>
                                {fulfillment.carrier}: {fulfillment.tracking_number}
                              </span>
                            )}
                          </div>
                          {trackingHref && (
                            <a
                              href={trackingHref}
                              target="_blank"
                              rel="noreferrer"
                              className="button secondary compact"
                            >
                              Track shipment <ExternalLink size={14} />
                            </a>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : data.tracking_number && (
                <div className="shipping-banner">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Truck size={24} className="shipping-banner-icon" />
                    <div>
                      <strong className="shipping-banner-title" style={{ display: 'block' }}>
                        Order Tracking Number: {data.tracking_number}
                      </strong>
                      <span className="shipping-banner-carrier">
                        Carrier: {carrierName} · Status: {data.status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <a
                    href={trackingUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="button secondary"
                    style={{
                      padding: '0.4rem 0.85rem',
                      fontSize: '0.85rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    Track on {carrierDisplay} <ExternalLink size={14} />
                  </a>
                </div>
              )}

              <OrderStatusTracker
                status={data.status}
                isDigital={isAllDigital}
                changedAt={data.status_updated_at}
              />

              <div className="checkout-layout">
                <section>
                  <h2>Your finds</h2>
                  {data.items.map((item, index) => (
                    <div className="order-item" key={index}>
                      <ProductImage src={item.image} alt={item.title} />
                      <div>
                        <Link href={`/products/${item.product}`}>{item.title}</Link>
                        <p>Quantity: {item.quantity}</p>
                        {item.is_digital ? (
                          <div className="digital-badge" style={{ marginTop: '6px' }}>
                            <small style={{ display: 'block', marginBottom: '4px' }}>
                              {['cancelled', 'refunded'].includes(data.status)
                                ? `Order ${data.status} — download access revoked`
                                : 'Digital download (Instant fulfillment)'}
                            </small>
                            {!['cancelled', 'refunded'].includes(data.status) && item.download_url ? (
                              <div className="form-actions">
                                <a
                                  className="button secondary"
                                  href={item.download_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  download
                                  style={{
                                    padding: '0.35rem 0.75rem',
                                    fontSize: '0.82rem',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '5px',
                                  }}
                                >
                                  <ArrowDownToLine size={14} />Download
                                </a>
                                {viewerKind(item.title) && (
                                  <button
                                    type="button"
                                    className="button"
                                    style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}
                                    onClick={() =>
                                      setViewer({
                                        url: item.download_url!,
                                        title: item.title,
                                        kind: viewerKind(item.title)!,
                                      })
                                    }
                                  >
                                    <Eye size={14} />View
                                  </button>
                                )}
                              </div>
                            ) : !['cancelled', 'refunded'].includes(data.status) ? (
                              <span className="muted" style={{ fontSize: '11px' }}>
                                Processing file link…
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                      <strong>{money(Number(item.unit_price) * item.quantity)}</strong>
                    </div>
                  ))}
                </section>

                <aside className="order-summary">
                  <h2>Order details</h2>
                  {!isAllDigital && (
                    <>
                      <h4>Deliver to</h4>
                      <p>
                        {data.address.address}<br />
                        {data.address.city}, {data.address.state}<br />
                        {data.address.country} {data.address.zip}
                      </p>
                    </>
                  )}
                  <h4>Payment status</h4>
                  <p>
                    {paymentMethod} · {paymentState()}
                  </p>
                  <div className="summary-total">
                    <span>Total</span>
                    <strong>{money(data.total)}</strong>
                  </div>
                  {activeRefund && (
                    <div
                      style={{
                        padding: '14px 16px',
                        borderRadius: '8px',
                        border: '1px solid var(--line)',
                        background: activeRefund.is_pending ? 'var(--green-light)' : 'var(--paper)',
                        marginTop: '1rem',
                        marginBottom: '1rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <strong
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontSize: '13px',
                            color: activeRefund.is_pending
                              ? 'var(--green)'
                              : activeRefund.status === 'approved'
                              ? 'var(--green)'
                              : activeRefund.status === 'declined'
                              ? 'var(--rose, #e11d48)'
                              : 'inherit',
                          }}
                        >
                          <RotateCcw size={15} />
                          {activeRefund.is_pending
                            ? 'Refund Request Pending Review'
                            : activeRefund.status === 'approved'
                            ? `Refund Approved (${money(activeRefund.refund_amount)})`
                            : activeRefund.status === 'declined'
                            ? 'Refund Request Declined'
                            : `Refund ${activeRefund.status}`}
                        </strong>
                        <Status value={activeRefund.status} />
                      </div>
                      <p style={{ margin: '4px 0', fontSize: '12px' }}>
                        <strong>Amount:</strong> {money(activeRefund.refund_amount)} &middot;{' '}
                        {activeRefund.refund_type === 'store_credit'
                          ? 'Instant Store Credit (Wallet)'
                          : 'Original Payment Method'}
                      </p>
                      <p style={{ margin: '4px 0', fontSize: '12px', color: 'var(--muted)' }}>
                        <strong>Reason:</strong> {activeRefund.reason}
                      </p>
                      {activeRefund.is_pending && (
                        <p style={{ margin: '6px 0 10px', fontSize: '11px', color: 'var(--muted)' }}>
                          {isRefundEditable
                            ? 'Physical returns are reviewed and processed within 1–2 business days. If you made a mistake or want to adjust items, you can edit your request below.'
                            : 'Your refund is processing with the payment provider and can no longer be edited.'}
                        </p>
                      )}
                      {(activeRefund.failure_reason || activeRefund.processing_reason) && activeRefund.status !== 'approved' && (
                        <p style={{ margin: '4px 0', fontSize: '11px', color: 'var(--rose, #e11d48)' }}>
                          <strong>Note:</strong> {activeRefund.failure_reason || activeRefund.processing_reason}
                        </p>
                      )}
                      {isRefundEditable && !requestingRefund && isWithin7Days && !['cancelled', 'refunded'].includes(data.status) && (
                        <button
                          type="button"
                          className="button secondary"
                          style={{ width: '100%', fontSize: '12px', padding: '7px 10px', marginTop: '6px' }}
                          onClick={openEditRefund}
                        >
                          Edit refund request
                        </button>
                      )}
                    </div>
                  )}
                  {canCancel && (
                    <button
                      type="button"
                      className="button secondary"
                      style={{ color: 'var(--rose, #e11d48)', borderColor: 'var(--rose, #e11d48)' }}
                      disabled={cancelling}
                      onClick={cancelOrder}
                    >
                      {cancelling ? 'Cancelling…' : 'Cancel order'}
                    </button>
                  )}
                  {canRequestRefund && !requestingRefund && (
                    <button className="button secondary" onClick={openNewRefund}>
                      <RotateCcw size={16} />Request a return / refund
                    </button>
                  )}
                  {requestingRefund && !['cancelled', 'refunded'].includes(data.status) && (
                    <form className="order-refund-form" onSubmit={submitRefund}>
                      <h4>{editingRefund ? 'Edit refund request' : 'Request refund (7-day window)'}</h4>
                      <fieldset className="order-refund-items">
                        <legend>Select items to return</legend>
                        {data.items.map((item) => {
                          const isClaimedByOther = claimedProductIds.includes(item.product) && !activeRefund?.product_ids?.includes(item.product);
                          const isClaimed = editingRefund ? isClaimedByOther : claimedProductIds.includes(item.product);
                          const isDisabled = !isWithinReturnWindow(item) || isClaimed;

                          return (
                            <label className="order-refund-item" key={item.product}>
                              <input
                                type="checkbox"
                                disabled={isDisabled}
                                checked={refundProducts.includes(item.product)}
                                onChange={(event) =>
                                  setRefundProducts((current) =>
                                    event.target.checked
                                      ? [...current, item.product]
                                      : current.filter((id) => id !== item.product)
                                  )
                                }
                              />
                              <span className="order-refund-item-copy">
                                <strong>{item.title}</strong>
                                <span className="muted">
                                  Quantity: {item.quantity} · {money(Number(item.unit_price) * item.quantity)}
                                </span>
                                {item.is_digital ? (
                                  <small>
                                    Digital products are non-refundable. If you are experiencing issues, please contact support via email.
                                  </small>
                                ) : isClaimed ? (
                                  <small style={{ color: 'var(--muted, #64748b)' }}>
                                    Refund already requested, processed, or declined for this item.
                                  </small>
                                ) : null}
                              </span>
                            </label>
                          );
                        })}
                      </fieldset>
                      <Field label="Refund destination">
                        <select value={refundType} onChange={(e) => setRefundType(e.target.value)}>
                          <option value="store_credit">ProAce Wallet credit</option>
                          <option value="original_payment">Original payment method</option>
                        </select>
                      </Field>
                      <Field label="Reason for return">
                        <select value={reason} onChange={(e) => setReason(e.target.value)} required>
                          <option value="item_damaged">Item damaged</option>
                          <option value="wrong_item_received">Wrong item received</option>
                          <option value="item_missing">Item missing</option>
                          <option value="other">Other</option>
                        </select>
                      </Field>
                      {reason === 'other' && (
                        <Field label="Describe the issue">
                          <textarea
                            value={otherReason}
                            onChange={(e) => setOtherReason(e.target.value)}
                            required
                            rows={3}
                          />
                        </Field>
                      )}
                      <div className="order-refund-actions">
                        <button className="button" disabled={busy || refundProducts.length === 0}>
                          {busy ? (editingRefund ? 'Updating…' : 'Submitting…') : (editingRefund ? 'Save changes' : 'Submit request')}
                        </button>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => {
                            setRequestingRefund(false);
                            setEditingRefund(false);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  )}
                  {hasPhysical && !isWithin7Days && (
                    <p className="fine-print">The 7-day return window for this order has closed.</p>
                  )}
                  {isAllDigital && (
                    <p className="fine-print">
                      Digital products are non-refundable. If you are experiencing issues, please contact support via email.
                    </p>
                  )}
                  {!requestingRefund && (
                    <Link className="button" href="/shop">
                      Keep discovering <ArrowRight size={16} />
                    </Link>
                  )}
                </aside>
              </div>
            </>
          )
        )}
        {viewer && (
          <div
            className="modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label={`Viewing ${viewer.title}`}
          >
            <section
              className="modal-card"
              style={{
                width: 'min(1000px, 94vw)',
                height: 'min(850px, 92vh)',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div className="modal-head">
                <div>
                  <span className="eyebrow green">YOUR DIGITAL PRODUCT</span>
                  <h2>{viewer.title}</h2>
                  <p className="muted">Private order viewer · You can download this file whenever you need it.</p>
                </div>
                <button className="icon-button" aria-label="Close viewer" onClick={() => setViewer(null)}>
                  <X size={18} />
                </button>
              </div>
              <div
                style={{
                  flex: 1,
                  minHeight: 0,
                  display: 'grid',
                  placeItems: 'center',
                  background: 'var(--soft)',
                  borderRadius: 6,
                  overflow: 'auto',
                }}
              >
                {viewer.kind === 'pdf' ? (
                  <iframe title={viewer.title} src={viewer.url} style={{ width: '100%', height: '100%', border: 0 }} />
                ) : (
                  <div style={{ position: 'relative', maxWidth: '100%', maxHeight: '100%' }}>
                    <ResponsiveMediaImage
                      src={viewer.url}
                      alt={viewer.title}
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                      detail
                    />
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </Gate>
  );
}
