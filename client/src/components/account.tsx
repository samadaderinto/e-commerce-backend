'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, ReactNode, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Bell, Check, ChevronRight, ExternalLink, Eye, EyeOff, FileText, Printer, Heart, LockKeyhole, LogOut, MapPin, Package, Pencil, Plus, RotateCcw, ShoppingBag, Settings, Store, Trash2, Truck, UserRound, WalletCards, X } from 'lucide-react';

import { api, money } from '@/lib/api';
import type { Address, Order, User, UserWallet } from '@/lib/types';
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
import { Empty, ErrorState, Field, Loading, ProductImage, Status } from './ui';

export function Gate({ children, next = '/account' }: { children: ReactNode; next?: string }) {
  const { user, sessionLoading } = useShop();
  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Make yourself at home" text="Sign in to keep your orders, addresses and good finds together." href={`/login?next=${encodeURIComponent(next)}`} label="Sign in" icon={<UserRound size={38} />} />;
  return <>{children}</>;
}

export function AuthPage({ mode }: { mode: string }) {
  const { login, user, notify } = useShop();
  const router = useRouter();
  const params = useSearchParams();
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const isRegister = mode === 'register';
  const isForgot = mode === 'forgot-password';
  const isReset = mode === 'reset-password';
  const verify = useQuery({ queryKey: ['verify', params.get('token')], queryFn: () => api<{detail: string}>('auth/verify', 'POST', { token: params.get('token') }), enabled: mode === 'verify-email', retry: false, staleTime: Infinity });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    try {
      if (isRegister) { const result = await api<{detail: string}>('auth/register', 'POST', data); setMessage(result.detail); }
      else if (isForgot) { const result = await api<{detail: string}>('auth/forgot', 'POST', data); setMessage(result.detail); }
      else if (isReset) { const result = await api<{detail: string}>('auth/reset', 'POST', { ...data, uid: params.get('uid'), token: params.get('token') }); setMessage(result.detail); }
      else { await login(data.email, data.password); const next = params.get('next') || '/account'; router.push(next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') ? next : '/account'); }
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <div className="auth-page container"><div className="auth-story"><span className="eyebrow">YOUR EVERYDAY, A LITTLE BETTER.</span><h2>Good things<br />start here.</h2><p>A place for your favourite finds.<br />And the ones you haven&apos;t found yet.</p><div className="auth-photo"><img src="https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85" alt="A minimal watch on a light background" /></div><span className="wordmark">proace<span>®</span></span></div><div className="auth-form-wrap">
    {mode === 'verify-email' ? <><div className="auth-icon"><Check /></div><h1>Email verification</h1>{verify.isLoading ? <Loading /> : verify.error ? <p className="form-error">{verify.error.message}</p> : <p>{verify.data?.detail}</p>}<Link className="button" href="/login">Continue to sign in <ArrowRight size={17} /></Link></> : message ? <><div className="auth-icon"><Check /></div><h1>{isReset ? 'A fresh start' : 'Check your inbox'}</h1><p>{message}</p><Link className="button" href="/login">Back to sign in <ArrowRight size={17} /></Link></> : <><span className="eyebrow green">{isRegister ? 'JOIN THE GOOD FINDS' : isForgot || isReset ? 'LET’S GET YOU BACK IN' : 'GOOD TO SEE YOU AGAIN'}</span><h1>{isRegister ? 'Make it yours.' : isForgot ? 'Forgot your password?' : isReset ? 'Set a new password' : 'Welcome back.'}</h1><p>{isRegister ? 'Create an account for a little more ProAce.' : isForgot ? 'We’ll send a reset link to your email address.' : isReset ? 'Choose a strong password for your account.' : 'Sign in to your everyday marketplace.'}</p><form onSubmit={submit} className="form-stack">{isRegister && <div className="form-row"><Field label="First name"><input name="first_name" required autoComplete="given-name" maxLength={30} /></Field><Field label="Last name"><input name="last_name" required autoComplete="family-name" maxLength={30} /></Field></div>}{!isReset && <Field label="Email address"><input name="email" type="email" required autoComplete="email" placeholder="you@example.com" /></Field>}{isRegister && <Field label="Phone number"><input name="phone1" type="tel" autoComplete="tel" required placeholder="+1 301 325 1550" /></Field>}{!isForgot && <Field label="Password"><div className="password-input"><input name="password" type={show ? 'text' : 'password'} required minLength={isRegister || isReset ? 8 : 1} maxLength={128} autoComplete={isRegister || isReset ? 'new-password' : 'current-password'} placeholder={isRegister ? 'At least 8 characters' : 'Your password'} /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></Field>}{!isRegister && !isForgot && !isReset && <Link href="/forgot-password" className="forgot-link">Forgot password?</Link>}{error && <p className="form-error" role="alert">{error}</p>}<button className="button" disabled={busy}>{busy ? 'One moment…' : isRegister ? 'Create account' : isForgot ? 'Send reset link' : isReset ? 'Update password' : 'Sign in'}<ArrowRight size={17} /></button></form><p className="auth-switch">{isRegister ? 'Already have an account?' : 'New around here?'} <Link href={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create an account'}</Link></p><p className="fine-print">By continuing, you agree to our <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</p></>}
    </div></div>;
}

export function AddressForm({
  onSaved,
  onCancel,
  initialData,
}: {
  onSaved: (address: Address) => void;
  onCancel?: () => void;
  initialData?: Address | null;
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
    <form className="form-stack address-form" onSubmit={submit}>
      <h3>{isEditing ? 'Edit delivery address' : 'Add a delivery address'}</h3>

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
            placeholder="e.g., 742 Evergreen Terrace or 123 Market Street"
            aria-invalid={!!streetError}
            aria-describedby={streetError ? 'street-address-error' : undefined}
          />
          {streetError && (
            <span id="street-address-error" className="address-field-error" role="alert">
              {streetError}
            </span>
          )}
        </Field>

        <Field label="Apt, Suite, Unit, Block (Optional)">
          <input
            name="unit"
            value={unitNumber}
            onChange={handleUnitChange}
            autoComplete="address-line2"
            maxLength={30}
            placeholder="e.g., Apt 4B, Suite 300, Block 12"
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

        <Field label="State / Province / Territory">
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

        <Field label="Postal / ZIP code">
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

function PasswordChangeModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
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
    setBusy(true);
    setError('');
    try {
      await api('password/change', 'POST', {
        current_password: currentPassword,
        password: newPassword,
      });
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="pwd-title" style={{ maxWidth: '440px' }}>
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
            <div style={{ position: 'relative' }}>
              <input
                type={showCurrent ? 'text' : 'password'}
                required
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="icon-button password-toggle"
                onClick={() => setShowCurrent(!showCurrent)}
                aria-label={showCurrent ? 'Hide current password' : 'Show current password'}
              >
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          <Field label="New password (min. 8 characters)">
            <div style={{ position: 'relative' }}>
              <input
                type={showNew ? 'text' : 'password'}
                required
                minLength={8}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="icon-button password-toggle"
                onClick={() => setShowNew(!showNew)}
                aria-label={showNew ? 'Hide new password' : 'Show new password'}
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
          <Field label="Confirm new password">
            <input
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions" style={{ marginTop: '16px' }}>
            <button type="button" className="button secondary" onClick={onClose}>Cancel</button>
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
  const orders = useQuery({ queryKey: ['orders', user?.id], queryFn: () => api<Order[]>('orders'), enabled: !!user });
  const addresses = useQuery({ queryKey: ['addresses', user?.id], queryFn: () => api<Address[]>('addresses'), enabled: !!user });
  const wallet = useQuery({ queryKey: ['wallet', user?.id], queryFn: () => api<UserWallet>('wallet'), enabled: !!user });
  function fundWallet() {
    setShowTopupModal(true);
  }
  useEffect(() => {
    const sessionId = params.get('topup_session_id');
    if (!sessionId || !user) return;
    void api<{ detail: string; balance: string }>('wallet/topup-confirm', 'POST', { session_id: sessionId })
      .then(result => { notify(result.detail); void client.invalidateQueries({ queryKey: ['wallet', user.id] }); router.replace('/account/wallet'); })
      .catch(error => notify((error as Error).message, true));
  }, [params, user?.id]);
  const links = [['overview', 'Overview', UserRound], ['orders', 'My orders', Package], ['wallet', 'ProAce Wallet', WalletCards], ['addresses', 'Address book', MapPin], ['profile', 'Personal details', UserRound]] as const;
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); try { const updated = await api<User>('me', 'PATCH', Object.fromEntries(new FormData(event.currentTarget))); client.setQueryData(['me'], updated); notify('Your details have been updated'); } catch (error) { notify((error as Error).message, true); } finally { setBusy(false); } }
  return <Gate><div className="container account-page"><div className="breadcrumb"><Link href="/">Home</Link><ChevronRight size={12} /><span>My account</span></div><div className="account-layout"><aside className="account-sidebar"><div className="account-avatar">{user?.first_name?.[0] || 'P'}</div><h2>{user?.first_name} {user?.last_name}</h2><p>{user?.email}</p><nav>{links.map(([key, name, Icon]) => <Link className={section === key ? 'active' : ''} key={key} href={key === 'overview' ? '/account' : `/account/${key}`}><Icon size={19} />{name}</Link>)}<Link href="/notifications"><Bell size={19} />Notifications</Link><Link href="/settings"><Settings size={19} />App settings</Link><Link href="/saved"><Heart size={19} />Saved items</Link><Link href="/merchant"><Store size={19} />Seller workspace<ArrowRight size={15} /></Link><button onClick={async () => { try { await logout(); router.push('/'); } catch (error) { notify((error as Error).message, true); } }}><LogOut size={19} />Sign out</button></nav></aside><div className="account-content">
    {section === 'overview' ? <><span className="eyebrow green">YOUR LITTLE CORNER OF PROACE</span><h1>Hello, {user?.first_name}.</h1><p className="muted">All your good finds, in one place.</p><div className="account-stat-grid"><Link href="/account/orders"><Package /><strong>{orders.data?.length || 0}</strong><span>Orders</span><ArrowRight size={17} /></Link><Link href="/account/wallet"><WalletCards /><strong>{money(wallet.data?.balance || '0.00')}</strong><span>Wallet balance</span><ArrowRight size={17} /></Link><Link href="/account/addresses"><MapPin /><strong>{addresses.data?.length || 0}</strong><span>Saved addresses</span><ArrowRight size={17} /></Link></div><div className="section-heading"><h2>Recent orders</h2><Link className="text-link" href="/account/orders">View all <ArrowRight size={16} /></Link></div><OrderList orders={orders.data?.slice(0, 3)} loading={orders.isLoading} error={orders.error} /></> : section === 'orders' ? <><h1>My orders</h1><p className="muted">Keep an eye on your latest finds.</p><OrderList orders={orders.data} loading={orders.isLoading} error={orders.error} /></> : section === 'wallet' ? <div><span className="eyebrow green">STORE CREDIT & BALANCES</span><h1>ProAce Wallet</h1><p className="muted">Use your available balance for instant 1-click purchases and immediate refund store credit.</p><div className="account-stat-grid" style={{ gridTemplateColumns: '1fr' }}><div className="stat-item stat-0 wallet-stat-card"><div><span style={{ fontWeight: 600 }}>Available Store Balance</span><WalletCards size={24} color="var(--green)" /></div><strong className="wallet-balance-amount">{money(wallet.data?.balance || '0.00')}</strong><small>Automatically available at checkout to pay for any product.</small></div></div><div className="section-heading" style={{ marginTop: '2rem' }}><h2>Recent wallet activity</h2><button className="button" onClick={fundWallet}>Add funds</button></div>{wallet.isLoading ? <Loading /> : wallet.error ? <ErrorState error={wallet.error} /> : !wallet.data?.transactions?.length ? <Empty title="No transactions yet" text="When you receive store credit or pay with your wallet, activity appears here." /> : <div className="table-scroll"><table><thead><tr><th>Date</th><th>Type</th><th>Source</th><th>Description</th><th>Amount</th></tr></thead><tbody>{wallet.data.transactions.map(tx => <tr key={tx.id}><td>{new Date(tx.created).toLocaleDateString()}</td><td><span className={tx.transaction_type === 'credit' ? 'status active' : 'status'}>{tx.transaction_type.toUpperCase()}</span></td><td>{tx.source}</td><td>{tx.description}</td><td style={{ fontWeight: 600, color: tx.transaction_type === 'credit' ? 'var(--green)' : 'var(--ink)' }}>{tx.transaction_type === 'credit' ? `+${money(tx.amount)}` : `-${money(tx.amount)}`}</td></tr>)}</tbody></table></div>}</div> : section === 'addresses' ? <><div className="section-heading"><h1>Address book</h1><button className="button" onClick={() => { setAdding(true); setEditingAddress(null); }}><Plus size={17} />Add address</button></div>{adding && <AddressForm onSaved={() => { setAdding(false); notify('Address saved'); }} onCancel={() => setAdding(false)} />}{editingAddress && <AddressForm initialData={editingAddress} onSaved={() => { setEditingAddress(null); notify('Address updated'); }} onCancel={() => setEditingAddress(null)} />}{addresses.isLoading ? <Loading /> : addresses.error ? <ErrorState error={addresses.error} /> : !addresses.data?.length && !adding && !editingAddress ? <div className="empty-state"><MapPin size={35} /><h2>Where should we send your finds?</h2><p>Add your first address to make checkout a little easier.</p></div> : <div className="address-grid">{addresses.data?.map(address => <article className="address-card" key={address.id}><div><MapPin size={18} />{address.is_default && <span className="status">Default address</span>}<div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}><button className="icon-button" aria-label={`Edit ${address.address}`} onClick={() => { setEditingAddress(address); setAdding(false); }}><Pencil size={15} /></button><button className="icon-button" aria-label={`Delete ${address.address}`} onClick={async () => { try { await api('addresses', 'DELETE', { id: address.id }); await client.invalidateQueries({ queryKey: ['addresses'] }); notify('Address removed'); } catch (error) { notify((error as Error).message, true); } }}><Trash2 size={16} /></button></div></div><strong>{address.address}</strong><p>{address.city}, {address.state}<br />{address.country}, {address.zip}</p><div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}><Link href={`/checkout?address_id=${address.id}`} className="text-link" style={{ fontSize: '11px', color: 'var(--green)' }}><span>Use for checkout</span><ArrowRight size={13} /></Link></div></article>)}</div>}</> : <><h1>Personal details</h1><p className="muted">A little about you.</p><form className="form-stack profile-form" onSubmit={save}><div className="form-row"><Field label="First name"><input name="first_name" defaultValue={user?.first_name} required maxLength={30} /></Field><Field label="Last name"><input name="last_name" defaultValue={user?.last_name} required maxLength={30} /></Field></div><Field label="Email address"><input value={user?.email || ''} disabled /></Field><Field label="Phone number"><input type="tel" name="phone1" defaultValue={user?.phone1} required /></Field><button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button><button type="button" className="text-link" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', display: 'inline-flex', alignItems: 'center', gap: '4px' }} onClick={() => setShowPasswordModal(true)}><span>Change your password</span><ArrowRight size={16} /></button></form></>}
    {showTopupModal && <WalletTopupModal onClose={() => setShowTopupModal(false)} onSuccess={url => { setShowTopupModal(false); window.location.assign(url); }} />}
    {showPasswordModal && <PasswordChangeModal onClose={() => setShowPasswordModal(false)} onSuccess={() => { setShowPasswordModal(false); notify('Password updated successfully'); }} />}
    </div></div></div></Gate>;
}

function OrderList({ orders, loading, error }: { orders?: Order[]; loading: boolean; error: Error | null }) {
  if (loading) return <Loading />; if (error) return <ErrorState error={error} />; if (!orders?.length) return <Empty title="Your first find is waiting" text="When you place an order, you can follow it right here." />;
  return <div className="order-list">{orders.map(order => <Link href={`/orders/${order.id}`} className="order-row" key={order.id}><ProductImage src={order.items[0]?.image} alt={order.items[0]?.title || 'Order'} /><div><strong>{order.reference}</strong><p>{order.items[0]?.title || 'Your order'}{order.items.length > 1 ? ` + ${order.items.length - 1} more` : ''}</p><small>{new Date(order.created).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</small></div><Status value={order.status} /><strong>{money(order.total)}</strong><ChevronRight size={18} /></Link>)}</div>;
}

export function OrderPage({ id }: { id: string }) {
  const { user, notify } = useShop(); const params = useSearchParams(); const client = useQueryClient();
  const order = useQuery({ queryKey: ['order', id, user?.id], queryFn: () => api<Order>(`orders/${id}`), enabled: !!user });
  const [requestingRefund, setRequestingRefund] = useState(false);
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
  const isAllDigital = data?.items?.every(item => item.is_digital) ?? false;
  const hasPhysical = data?.items?.some(item => !item.is_digital) ?? false;
  const createdTime = data ? new Date(data.created).getTime() : 0;
  const daysElapsed = (Date.now() - createdTime) / (1000 * 60 * 60 * 24);
  const isWithin7Days = daysElapsed <= 7;
  const canRequestRefund = hasPhysical && isWithin7Days && !['refunded', 'refund_requested', 'cancelled'].includes(data?.status || '');

  async function submitRefund(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api(`orders/${id}/refund`, 'POST', { reason, other_reason: reason === 'other' ? otherReason : '', product_ids: refundProducts, refund_type: refundType });
      await client.invalidateQueries({ queryKey: ['order', id] });
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['wallet'] });
      notify('Refund request submitted. We will review your return within 1–2 business days.');
      setRequestingRefund(false);
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

  const canCancel = ['pending', 'confirmed'].includes(data?.status || '') && data?.status !== 'cancelled';
  const [cancelling, setCancelling] = useState(false);

  async function cancelOrder() {
    if (!window.confirm('Are you sure you want to cancel this order? Any payment made will be refunded directly to your ProAce Wallet.')) {
      return;
    }
    setCancelling(true);
    try {
      await api(`orders/${id}/cancel`, 'POST');
      await client.invalidateQueries({ queryKey: ['order', id] });
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['wallet'] });
      notify('Order cancelled successfully. Refund has been credited to your wallet.');
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setCancelling(false);
    }
  }

  return <Gate next={`/orders/${id}`}><div className="container order-detail"><Link className="text-link" href="/account/orders"><ArrowLeft size={16} />All orders</Link>{order.isLoading ? <Loading /> : order.error ? <ErrorState error={order.error} /> : data && <><div className="order-success"><div className="success-icon"><Check size={30} /></div><span className="eyebrow green">{params.has('placed') ? 'A GOOD FIND, INDEED' : 'YOUR ORDER'}</span><h1>{params.has('placed') ? 'It’s on the list.' : data.reference}</h1><p>{params.has('placed') ? `Your order ${data.reference} is confirmed. Thank you for shopping with ProAce.` : `Placed on ${new Date(data.created).toLocaleDateString()}`}</p><Status value={data.status} /><button type="button" className="button secondary receipt-print-button" onClick={() => window.print()}><Printer size={16} />Print receipt</button></div>
  {data.tracking_number && <div className="shipping-banner">
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <Truck size={24} className="shipping-banner-icon" />
      <div>
        <strong className="shipping-banner-title" style={{ display: 'block' }}>Order Tracking Number: {data.tracking_number}</strong>
        <span className="shipping-banner-carrier">Carrier: {carrierName} · Status: {data.status.toUpperCase()}</span>
      </div>
    </div>
    <a href={trackingUrl} target="_blank" rel="noreferrer" className="button secondary" style={{ padding: '0.4rem 0.85rem', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
      Track on {carrierDisplay} <ExternalLink size={14} />
    </a>
  </div>}
  <div className="order-progress">{['confirmed', 'shipped', 'delivered'].map((step, index) => <div key={step} className={['confirmed', 'shipped', 'delivered'].indexOf(data.status) >= index ? 'done' : ''}><span><Check size={15} /></span><strong>{step}</strong></div>)}</div><div className="checkout-layout"><section><h2>Your finds</h2>{data.items.map((item, index) => <div className="order-item" key={index}><ProductImage src={item.image} alt={item.title} /><div><Link href={`/products/${item.product}`}>{item.title}</Link><p>Quantity: {item.quantity}</p>{item.is_digital ? <div className="digital-badge" style={{ marginTop: '6px' }}><small style={{ display: 'block', marginBottom: '4px' }}>Digital download (Instant fulfillment)</small>{item.download_url ? <div className="form-actions"><a className="button secondary" href={item.download_url} target="_blank" rel="noreferrer" download style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '5px' }}><ArrowDownToLine size={14} />Download</a>{viewerKind(item.title) && <button type="button" className="button" style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }} onClick={() => setViewer({ url: item.download_url!, title: item.title, kind: viewerKind(item.title)! })}><Eye size={14} />View</button>}</div> : <span className="muted" style={{ fontSize: '11px' }}>Processing file link…</span>}</div> : null}</div><strong>{money(Number(item.unit_price) * item.quantity)}</strong></div>)}</section><aside className="order-summary"><h2>Order details</h2><h4>Deliver to</h4><p>{data.address.address}<br />{data.address.city}, {data.address.state}<br />{data.address.country} {data.address.zip}</p><h4>Payment status</h4><p>{data.payment_type === 'user_wallet' ? 'ProAce Wallet Balance (Paid)' : data.payment_type === 'stripe_wallet' ? 'Cards, Stripe & Wallet (Paid)' : data.payment_type === 'card' ? 'Card (Paid)' : 'Online Payment (Paid)'}</p><div className="summary-total"><span>Total</span><strong>{money(data.total)}</strong></div>{canCancel && <button type="button" className="button secondary" style={{ color: 'var(--rose, #e11d48)', borderColor: 'var(--rose, #e11d48)' }} disabled={cancelling} onClick={cancelOrder}>{cancelling ? 'Cancelling…' : 'Cancel order'}</button>}{canRequestRefund && !requestingRefund && <button className="button secondary" onClick={() => setRequestingRefund(true)}><RotateCcw size={16} />Request a return / refund</button>}{requestingRefund && <form className="form-stack" onSubmit={submitRefund} style={{ marginTop: '1rem' }}><h4>Request refund (7-day window)</h4><fieldset className="form-stack"><legend>Select items to return</legend>{data.items.map(item => <label className="check-row" key={item.product}><input type="checkbox" disabled={Boolean(item.is_digital)} checked={refundProducts.includes(item.product)} onChange={event => setRefundProducts(current => event.target.checked ? [...current, item.product] : current.filter(id => id !== item.product))} />{item.title} · {money(Number(item.unit_price) * item.quantity)}{item.is_digital && <small>Digital products are non-refundable. If you are experiencing issues, please contact support via email.</small>}</label>)}</fieldset><Field label="Refund Destination"><select value={refundType} onChange={e => setRefundType(e.target.value)}><option value="store_credit">Instant ProAce Store Credit (Wallet)</option><option value="original_payment">Original Payment Method (Card / Bank)</option></select></Field><Field label="Reason for return"><select value={reason} onChange={e => setReason(e.target.value)} required><option value="item_damaged">Item damaged</option><option value="wrong_item_received">Wrong item received</option><option value="item_missing">Item missing</option><option value="other">Other</option></select></Field>{reason === 'other' && <Field label="Describe the issue"><textarea value={otherReason} onChange={e => setOtherReason(e.target.value)} required rows={3} /></Field>}<div className="form-row"><button className="button" disabled={busy || refundProducts.length === 0}>{busy ? 'Submitting…' : 'Submit request'}</button><button type="button" className="button secondary" onClick={() => setRequestingRefund(false)}>Cancel</button></div></form>}{hasPhysical && !isWithin7Days && <p className="fine-print">The 7-day return window for this order has closed.</p>}{isAllDigital && <p className="fine-print">Digital products are non-refundable. If you are experiencing issues, please contact support via email.</p>}<Link className="button" href="/shop">Keep discovering <ArrowRight size={16} /></Link></aside></div></>}{viewer && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={`Viewing ${viewer.title}`}><section className="modal-card" style={{ width: 'min(1000px, 94vw)', height: 'min(850px, 92vh)', display: 'flex', flexDirection: 'column' }}><div className="modal-head"><div><span className="eyebrow green">YOUR DIGITAL PRODUCT</span><h2>{viewer.title}</h2><p className="muted">Private order viewer · You can download this file whenever you need it.</p></div><button className="icon-button" aria-label="Close viewer" onClick={() => setViewer(null)}><X size={18} /></button></div><div style={{ flex: 1, minHeight: 0, display: 'grid', placeItems: 'center', background: 'var(--soft)', borderRadius: 6, overflow: 'auto' }}>{viewer.kind === 'pdf' ? <iframe title={viewer.title} src={viewer.url} style={{ width: '100%', height: '100%', border: 0 }} /> : <div style={{ position: 'relative', maxWidth: '100%', maxHeight: '100%' }}><img src={viewer.url} alt={viewer.title} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} /></div>}</div></section></div>}</div></Gate>;

}
