"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useShop } from "./providers";
import { PayoutAccountFilters, type PayoutAccountSort } from "./payout-account-filters";
import { useDebouncedValue } from "./collection-filters";
import { ErrorState, Field, Loading, useDialogFocus } from "./ui";

type StripeDestination = {
  id: number;
  label: string;
  account_id_last4: string;
  is_default: boolean;
};

type DestinationEditor = StripeDestination | "new" | null;

export function StripePayoutDestinations({
  pickerOnly = false,
  selectedId,
  onSelect,
}: {
  pickerOnly?: boolean;
  selectedId?: number | null;
  onSelect?: (id: number) => void;
}): React.JSX.Element {
  const { user, notify } = useShop();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<DestinationEditor>(null);
  const [busy, setBusy] = useState(false);
  const mutationInFlight = useRef(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [defaultOnly, setDefaultOnly] = useState(false);
  const [sort, setSort] = useState<PayoutAccountSort>("recent");
  const [selectorOpen, setSelectorOpen] = useState(false);
  const selectorDialogRef = useDialogFocus(selectorOpen, () => setSelectorOpen(false));
  const dialogRef = useDialogFocus(Boolean(editing), () => {
    if (!busy) setEditing(null);
  });
  const destinations = useQuery({
    queryKey: ["stripe-payout-destinations", user?.id],
    queryFn: () => api<StripeDestination[]>("stripe-payout-destinations"),
    enabled: Boolean(user),
  });
  const selected = selectedId && selectedId > 0
    ? selectedId
    : destinations.data?.find(item => item.is_default)?.id;
  const selectedDestination = destinations.data?.find(item => item.id === selected);

  useEffect(() => {
    if (!onSelect || !destinations.data) return;
    const currentExists = destinations.data.some(destination => destination.id === selectedId);
    if (currentExists) return;
    const fallback = destinations.data.find(destination => destination.is_default)?.id || 0;
    if ((selectedId || 0) !== fallback) onSelect(fallback);
  }, [destinations.data, selectedId, onSelect]);

  async function save(): Promise<void> {
    if (busy || !dialogRef.current) return;
    const inputs = dialogRef.current.querySelectorAll<HTMLInputElement>("input");
    const values = new FormData();
    for (const input of inputs) {
      if (!input.reportValidity()) return;
      if (input.type !== "checkbox" || input.checked) {
        values.set(input.name, input.type === "checkbox" ? "on" : input.value.trim());
      }
    }
    const payload: Record<string, string | boolean> = {
      label: String(values.get("label") || ""),
      is_default: values.get("is_default") === "on",
    };
    const stripeAccountId = String(values.get("stripe_account_id") || "").trim();
    if (stripeAccountId) payload.stripe_account_id = stripeAccountId;

    setBusy(true);
    setError("");
    try {
      const saved = await api<StripeDestination>(
        editing && editing !== "new"
          ? `stripe-payout-destinations/${editing.id}`
          : "stripe-payout-destinations",
        editing && editing !== "new" ? "PATCH" : "POST",
        payload,
      );
      await queryClient.invalidateQueries({ queryKey: ["stripe-payout-destinations"] });
      onSelect?.(saved.id);
      setEditing(null);
      notify(editing && editing !== "new" ? "Stripe destination updated." : "Stripe destination saved securely.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Unable to save the Stripe destination.");
    } finally {
      setBusy(false);
    }
  }

  async function change(destination: StripeDestination, remove: boolean): Promise<void> {
    if (mutationInFlight.current || busy) return;
    if (remove && !window.confirm(`Delete ${destination.label}?`)) return;
    mutationInFlight.current = true;
    setBusy(true);
    try {
      await api(
        `stripe-payout-destinations/${destination.id}`,
        remove ? "DELETE" : "PATCH",
        remove ? undefined : { is_default: true },
      );
      await queryClient.invalidateQueries({ queryKey: ["stripe-payout-destinations"] });
      if (remove && selectedId === destination.id) onSelect?.(0);
      if (!remove) onSelect?.(destination.id);
      notify(remove ? "Payout account deleted." : "Default payout account updated.");
    } catch (reason: unknown) {
      notify(reason instanceof Error ? reason.message : "Unable to update the Stripe destination.", true);
    } finally {
      mutationInFlight.current = false;
      setBusy(false);
    }
  }

  const visible = (destinations.data || []).filter(destination =>
    (!defaultOnly || destination.is_default) &&
    `${destination.label} ${destination.account_id_last4}`.toLowerCase().includes(debouncedSearch.trim().toLowerCase()),
  ).sort((left, right) => sort === "name" ? left.label.localeCompare(right.label) : right.id - left.id);
  const initial = editing && editing !== "new" ? editing : null;
  return (
    <section className={`merchant-section stripe-payout-destinations${pickerOnly ? " stripe-destination-picker" : ""}`}>
      {!pickerOnly && (
        <div className="section-heading">
          <div>
            <h2>Stripe transfer destinations</h2>
            <p>Save a connected Stripe account for treasury transfer requests.</p>
          </div>
          <button type="button" className="button secondary compact" onClick={() => { setEditing("new"); setError(""); }}>
            Add Stripe account
          </button>
        </div>
      )}
      {!pickerOnly && Boolean(destinations.data?.length) && (
        <PayoutAccountFilters
          search={search}
          onSearch={setSearch}
          defaultOnly={defaultOnly}
          onDefaultOnly={setDefaultOnly}
          sort={sort}
          onSort={setSort}
          placeholder="Search label or account’s last 4 characters…"
          count={visible.length}
          total={destinations.data?.length || 0}
        />
      )}
      {destinations.isLoading ? (
        <Loading compact />
      ) : destinations.error ? (
        <ErrorState error={destinations.error} />
      ) : !pickerOnly && !visible.length ? (
        <div className="payout-destination-empty">
          <h2>{destinations.data?.length ? "No matching Stripe accounts" : "No Stripe destinations yet"}</h2>
          <p>
            {pickerOnly
              ? "Save a Stripe destination on the Payout accounts page before requesting this transfer."
              : destinations.data?.length
                ? "Try another search or clear the filters above."
                : "Add a connected Stripe account ID to select it for treasury transfer requests."}
          </p>
          {pickerOnly && (
            <button type="button" className="button secondary compact" onClick={() => { setEditing("new"); setError(""); }}>
              Add Stripe account
            </button>
          )}
        </div>
      ) : pickerOnly ? (
        <div className="payout-picker-control">
          {selectedDestination ? (
            <div className="payout-selected-summary">
              <div>
                <strong>{selectedDestination.label}{selectedDestination.is_default ? " · Default" : ""}</strong>
                <p>Connected account · …{selectedDestination.account_id_last4}</p>
              </div>
              <button type="button" className="button secondary compact" onClick={() => setSelectorOpen(true)}>
                Change
              </button>
            </div>
          ) : (
            <div className="payout-selected-summary">
              <div>
                <strong>Stripe account</strong>
                <p>Choose a saved account or add a new one.</p>
              </div>
              <button
                type="button"
                className="button secondary compact"
                onClick={() => setSelectorOpen(true)}
              >
                Choose account
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="stripe-destination-list">
          {visible.map(destination => (
            <article className="address-card stripe-destination-card" key={destination.id}>
              <div>
                <strong>{destination.label}{destination.is_default && <span className="payout-default-badge">Default Stripe account</span>}</strong>
                <p>Connected account · …{destination.account_id_last4}</p>
              </div>
              <details className="payout-account-menu">
                <summary>Actions</summary>
                <div className="payout-account-menu-items">
                  <button type="button" className="button secondary compact" onClick={() => { setEditing(destination); setError(""); }}>Edit</button>
                  <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(destination, true)}>Delete</button>
                  {!destination.is_default && (
                    <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(destination, false)}>Set as default</button>
                  )}
                </div>
              </details>
            </article>
          ))}
        </div>
      )}
      {selectorOpen && pickerOnly && (
        <div
          className="checkout-modal-backdrop"
          role="presentation"
          onMouseDown={event => event.target === event.currentTarget && setSelectorOpen(false)}
        >
          <section ref={selectorDialogRef} className="checkout-address-modal payout-selector-modal" role="dialog" aria-modal="true" aria-labelledby="stripe-selector-title">
            <div className="checkout-modal-head">
              <div>
                <span className="eyebrow green">PAYOUT DESTINATION</span>
                <h2 id="stripe-selector-title">Select Stripe account</h2>
                <p className="muted payout-selector-hint">Choose the saved connected account for this transfer.</p>
              </div>
              <button type="button" className="icon-button" aria-label="Close Stripe account selector" onClick={() => setSelectorOpen(false)}>×</button>
            </div>
            <div className="checkout-modal-body">
              <div className="checkout-modal-address-list">
                {!destinations.data?.length && <p className="payout-selector-empty">No saved accounts yet. Add one below.</p>}
                {destinations.data?.map(destination => {
                  const isSelected = destination.id === selected;
                  return (
                    <div className="payout-option-row" key={destination.id}>
                      <button
                        type="button"
                        className={`checkout-modal-address-card payout-destination-option${isSelected ? " selected" : ""}`}
                        onClick={() => { onSelect?.(destination.id); setSelectorOpen(false); }}
                      >
                        <span className="modal-address-radio"><span className={`radio-dot${isSelected ? " active" : ""}`}>{isSelected ? "✓" : ""}</span></span>
                        <span className="modal-address-info">
                          <span className="modal-address-badges"><strong>{destination.label}</strong>{destination.is_default && <span className="status">Default</span>}{isSelected && <span className="status status-selected">Selected</span>}</span>
                          <span className="payout-option-details">Connected account · …{destination.account_id_last4}</span>
                        </span>
                      </button>
                      <div className="payout-option-actions" aria-label={`${destination.label} account actions`}>
                        <button type="button" className="button secondary compact" onClick={() => { setSelectorOpen(false); setEditing(destination); setError(""); }}>Edit</button>
                        {!destination.is_default && <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(destination, false)}>Set default</button>}
                        <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(destination, true)}>Delete</button>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="checkout-modal-footer">
                <button type="button" className="button secondary payout-add-option" onClick={() => { setSelectorOpen(false); setEditing("new"); setError(""); }}>
                  + Add a new Stripe account
                </button>
                <Link className="text-link payout-manage-link" href="/account/payout-accounts">Manage payout accounts</Link>
              </div>
            </div>
          </section>
        </div>
      )}
      {editing && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={event => event.target === event.currentTarget && !busy && setEditing(null)}>
          <section ref={dialogRef} className="dialog-card bank-account-dialog" role="dialog" aria-modal="true" aria-labelledby="stripe-destination-dialog-title">
            <div className="section-heading">
              <div>
                <span className="eyebrow green">STRIPE TRANSFER DESTINATION</span>
                <h2 id="stripe-destination-dialog-title">{initial ? "Edit Stripe account" : "Add Stripe account"}</h2>
              </div>
              <button type="button" className="button secondary compact" aria-label="Close Stripe destination dialog" disabled={busy} onClick={() => setEditing(null)}>×</button>
            </div>
            <Field label="Account label">
              <input name="label" defaultValue={initial?.label} required maxLength={120} placeholder="e.g. ProAce treasury transfers" />
            </Field>
            <Field label="Stripe connected account ID">
              <input name="stripe_account_id" required={!initial} pattern="acct_[A-Za-z0-9]{8,}" autoComplete="off" placeholder={initial ? `Unchanged · ending ${initial.account_id_last4}` : "acct_…"} />
            </Field>
            <label className="check-row">
              <input name="is_default" type="checkbox" defaultChecked={initial?.is_default} />
              Default Stripe destination
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="form-actions">
              <button type="button" className="button" disabled={busy} onClick={() => void save()}>{busy ? "Saving…" : "Save Stripe account"}</button>
              <button type="button" className="button secondary" disabled={busy} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
