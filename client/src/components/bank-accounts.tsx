"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useShop } from "./providers";
import { ErrorState, Field, Loading, useDialogFocus } from "./ui";
import { PayoutAccountFilters, type PayoutAccountSort } from "./payout-account-filters";
import { useDebouncedValue } from "./collection-filters";

type BankAccount = {
  id: number;
  bank_name: string;
  account_holder_name: string;
  account_last4: string;
  routing_last4: string;
  is_default: boolean;
};

export function BankAccounts({
  onSelect,
  selectedId,
  compact = false,
  pickerOnly = false,
  heading = "Bank accounts",
}: {
  onSelect?: (id: number) => void;
  selectedId?: number | null;
  compact?: boolean;
  pickerOnly?: boolean;
  heading?: string;
}): React.JSX.Element {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [editing, setEditing] = useState<BankAccount | "new" | null>(null);
  const [busy, setBusy] = useState(false);
  const mutationInFlight = useRef(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [defaultOnly, setDefaultOnly] = useState(false);
  const [sort, setSort] = useState<PayoutAccountSort>("recent");
  const [selectorOpen, setSelectorOpen] = useState(false);
  const selectorDialogRef = useDialogFocus(selectorOpen, () => setSelectorOpen(false));
  const editorDialogRef = useDialogFocus(Boolean(editing), () => {
    if (!busy) setEditing(null);
  });
  const accounts = useQuery({
    queryKey: ["bank-accounts", user?.id],
    queryFn: () => api<BankAccount[]>("bank-accounts"),
    enabled: !!user,
  });
  const selected =
    selectedId && selectedId > 0
      ? selectedId
      : accounts.data?.find((account) => account.is_default)?.id;
  const selectedAccount = accounts.data?.find((account) => account.id === selected);
  useEffect(() => {
    if (!onSelect || !accounts.data) return;
    const currentExists = accounts.data.some(account => account.id === selectedId);
    if (currentExists) return;
    const fallback = accounts.data.find(account => account.is_default)?.id || 0;
    if ((selectedId || 0) !== fallback) onSelect(fallback);
  }, [accounts.data, selectedId, onSelect]);

  async function save(): Promise<void> {
    if (busy) return;
    const fields =
      editorDialogRef.current?.querySelectorAll<HTMLInputElement>("input");
    if (!fields) return;
    const values = new FormData();
    for (const input of fields) {
      if (!input.reportValidity()) return;
      if (input.type !== "checkbox" || input.checked)
        values.set(input.name, input.type === "checkbox" ? "on" : input.value);
    }
    const payload: Record<string, string | boolean> = {
      bank_name: String(values.get("bank_name") || ""),
      account_holder_name: String(values.get("account_holder_name") || ""),
      is_default: values.get("is_default") === "on",
    };
    for (const field of ["account_number", "routing_number"]) {
      const value = String(values.get(field) || "").trim();
      if (value) payload[field] = value;
    }
    setBusy(true);
    setError("");
    try {
      const account = await api<BankAccount>(
        editing && editing !== "new"
          ? `bank-accounts/${editing.id}`
          : "bank-accounts",
        editing && editing !== "new" ? "PATCH" : "POST",
        payload,
      );
      await client.invalidateQueries({ queryKey: ["bank-accounts"] });
      onSelect?.(account.id);
      setEditing(null);
      notify(initial ? "Payout account updated." : "Payout account saved securely.");
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to save bank account.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function change(account: BankAccount, remove: boolean): Promise<void> {
    if (mutationInFlight.current || busy) return;
    if (
      remove &&
      !window.confirm(
        `Delete ${account.bank_name} account ending ${account.account_last4}?`,
      )
    )
      return;
    mutationInFlight.current = true;
    setBusy(true);
    try {
      await api(
        `bank-accounts/${account.id}`,
        remove ? "DELETE" : "PATCH",
        remove ? undefined : { is_default: true },
      );
      await client.invalidateQueries({ queryKey: ["bank-accounts"] });
      if (remove && selectedId === account.id) onSelect?.(0);
      if (!remove) onSelect?.(account.id);
      notify(remove ? "Payout account deleted." : "Default payout account updated.");
    } catch (reason: unknown) {
      notify(
        reason instanceof Error
          ? reason.message
          : "Unable to update bank account.",
        true,
      );
    } finally {
      mutationInFlight.current = false;
      setBusy(false);
    }
  }

  const visible = (accounts.data || []).filter(
    (account) =>
      (!defaultOnly || account.is_default) &&
      `${account.bank_name} ${account.account_holder_name} ${account.account_last4}`
        .toLowerCase()
        .includes(debouncedSearch.trim().toLowerCase()),
  ).sort((left, right) => sort === "name" ? left.bank_name.localeCompare(right.bank_name) : right.id - left.id);
  const initial = editing && editing !== "new" ? editing : null;
  return (
    <section className={`merchant-section bank-accounts${compact ? " bank-accounts-compact" : ""}${pickerOnly ? " bank-accounts-picker" : ""}`}>
      {!pickerOnly && <div className="section-heading">
        <h2>{heading}</h2>
        <button
          type="button"
          className={`button secondary${compact ? " compact" : ""}`}
          onClick={() => {
            setEditing("new");
            setError("");
          }}
        >
          Add bank account
        </button>
      </div>}
      {!onSelect && !pickerOnly && Boolean(accounts.data?.length) && (
        <PayoutAccountFilters
          search={search}
          onSearch={setSearch}
          defaultOnly={defaultOnly}
          onDefaultOnly={setDefaultOnly}
          sort={sort}
          onSort={setSort}
          placeholder="Search bank, account holder, or last 4 digits…"
          count={visible.length}
          total={accounts.data?.length || 0}
        />
      )}
      {accounts.isLoading ? (
        <Loading />
      ) : accounts.error ? (
        <ErrorState error={accounts.error} />
      ) : !pickerOnly && !visible.length ? (
        <div className="payout-destination-empty">
          <h2>{pickerOnly ? "No bank accounts saved" : "No bank accounts found"}</h2>
          <p>
            {accounts.data?.length
              ? "No bank accounts match these filters. Reset the search or default filter."
              : pickerOnly
                ? "Save a bank account on the Payout accounts page before requesting a bank transfer."
                : "Add a bank account to use it for withdrawals."}
          </p>
          {accounts.data?.length ? (
            <button
              type="button"
              className="text-button"
              onClick={() => { setSearch(""); setDefaultOnly(false); }}
            >
              Reset filters
            </button>
          ) : pickerOnly ? (
            <button type="button" className="button secondary compact" onClick={() => { setEditing("new"); setError(""); }}>
              Add bank account
            </button>
          ) : null}
        </div>
      ) : pickerOnly ? (
        <div className="payout-picker-control">
          {selectedAccount ? (
            <div className="payout-selected-summary">
              <div>
                <strong>{selectedAccount.bank_name}{selectedAccount.is_default ? " · Default" : ""}</strong>
                <p>{selectedAccount.account_holder_name} · Account ••••{selectedAccount.account_last4}</p>
              </div>
              <button type="button" className="button secondary compact" onClick={() => setSelectorOpen(true)}>
                Change
              </button>
            </div>
          ) : (
            <div className="payout-selected-summary">
              <div>
                <strong>Bank account</strong>
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
        <div className="address-grid">
          {visible.map((account) => (
            <article className="address-card bank-account-card" key={account.id}>
              {onSelect && (
                <label className="check-row">
                  <input
                    type="radio"
                    name="saved_bank_account"
                    checked={selected === account.id}
                    onChange={() => onSelect(account.id)}
                    required
                  />
                  Use this account
                </label>
              )}
              <strong>
                {account.bank_name}
                {account.is_default && <span className="payout-default-badge">Default bank account</span>}
              </strong>
              <p>{account.account_holder_name}</p>
              <p>
                Account ••••{account.account_last4} · Routing ••••
                {account.routing_last4}
              </p>
              <details className="payout-account-menu">
                <summary>Actions</summary>
                <div className="payout-account-menu-items">
                  <button
                    type="button"
                    className={`button secondary${compact ? " compact" : ""}`}
                    onClick={() => {
                      setEditing(account);
                      setError("");
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={`button secondary${compact ? " compact" : ""}`}
                    disabled={busy} onClick={() => void change(account, true)}
                  >
                    Delete
                  </button>
                  {!account.is_default && (
                    <button
                      type="button"
                      className={`button secondary${compact ? " compact" : ""}`}
                      disabled={busy} onClick={() => void change(account, false)}
                    >
                      Set as default
                    </button>
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
          <section ref={selectorDialogRef} className="checkout-address-modal payout-selector-modal" role="dialog" aria-modal="true" aria-labelledby="bank-selector-title">
            <div className="checkout-modal-head">
              <div>
                <span className="eyebrow green">PAYOUT DESTINATION</span>
                <h2 id="bank-selector-title">Select bank account</h2>
                <p className="muted payout-selector-hint">Choose the saved account for this withdrawal.</p>
              </div>
              <button type="button" className="icon-button" aria-label="Close bank account selector" onClick={() => setSelectorOpen(false)}>×</button>
            </div>
            <div className="checkout-modal-body">
              <div className="checkout-modal-address-list">
                {!visible?.length && <p className="payout-selector-empty">No saved accounts yet. Add one below.</p>}
                {visible.map(account => {
                  const isSelected = account.id === selected;
                  return (
                    <div className="payout-option-row" key={account.id}>
                      <button
                        type="button"
                        className={`checkout-modal-address-card payout-destination-option${isSelected ? " selected" : ""}`}
                        onClick={() => { onSelect?.(account.id); setSelectorOpen(false); }}
                      >
                        <span className="modal-address-radio"><span className={`radio-dot${isSelected ? " active" : ""}`}>{isSelected ? "✓" : ""}</span></span>
                        <span className="modal-address-info">
                          <span className="modal-address-badges"><strong>{account.bank_name}</strong>{account.is_default && <span className="status">Default</span>}{isSelected && <span className="status status-selected">Selected</span>}</span>
                          <span className="payout-option-details">{account.account_holder_name} · Account ••••{account.account_last4} · Routing ••••{account.routing_last4}</span>
                        </span>
                      </button>
                      <div className="payout-option-actions" aria-label={`${account.bank_name} account actions`}>
                        <button type="button" className="button secondary compact" onClick={() => { setSelectorOpen(false); setEditing(account); setError(""); }}>Edit</button>
                        {!account.is_default && <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(account, false)}>Set default</button>}
                        <button type="button" className="button secondary compact" disabled={busy} onClick={() => void change(account, true)}>Delete</button>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="checkout-modal-footer">
                <button type="button" className="button secondary payout-add-option" onClick={() => { setSelectorOpen(false); setEditing("new"); setError(""); }}>
                  + Add a new bank account
                </button>
                <Link className="text-link payout-manage-link" href="/account/payout-accounts">Manage payout accounts</Link>
              </div>
            </div>
          </section>
        </div>
      )}
      {editing && (
        <div
          className="dialog-backdrop"
          role="presentation"
          onMouseDown={event =>
            event.target === event.currentTarget && !busy && setEditing(null)
          }
        >
          <section
            key={initial?.id || "new"}
            ref={editorDialogRef}
            className="dialog-card bank-account-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bank-account-dialog-title"
            onKeyDown={event => {
              if (
                event.key === "Enter" &&
                event.target instanceof HTMLInputElement
              ) {
                event.preventDefault();
                event.stopPropagation();
                void save();
              }
            }}
          >
            <div className="section-heading">
              <div>
                <span className="eyebrow green">PAYOUT DESTINATION</span>
                <h2 id="bank-account-dialog-title">
                  {initial ? "Edit bank account" : "Add bank account"}
                </h2>
              </div>
              <button
                type="button"
                className="button secondary compact"
                aria-label="Close bank account dialog"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                ×
              </button>
            </div>
            <Field label="Bank name">
              <input
                name="bank_name"
                defaultValue={initial?.bank_name}
                required
                maxLength={120}
              />
            </Field>
            <Field label="Account holder">
              <input
                name="account_holder_name"
                defaultValue={initial?.account_holder_name}
                required
                maxLength={160}
              />
            </Field>
            <Field label="Account number">
              <input
                name="account_number"
                inputMode="numeric"
                pattern="[0-9]{4,34}"
                required={!initial}
                autoComplete="off"
                placeholder={
                  initial ? `Unchanged · ending ${initial.account_last4}` : ""
                }
              />
            </Field>
            <Field label="Routing number">
              <input
                name="routing_number"
                inputMode="numeric"
                pattern="[0-9]{4,12}"
                required={!initial}
                autoComplete="off"
                placeholder={
                  initial ? `Unchanged · ending ${initial.routing_last4}` : ""
                }
              />
            </Field>
            <label className="check-row">
              <input
                name="is_default"
                type="checkbox"
                defaultChecked={initial?.is_default}
              />
              Default payout account
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="form-actions">
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => void save()}
              >
                {busy ? "Saving…" : "Save bank account"}
              </button>
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

