"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, money } from "@/lib/api";
import type {
  AdminReferral,
  AdminReferralPage,
  AffiliateOperator,
  AffiliateOperatorPage,
  ReferralWorkspace,
} from "@/lib/types";
import { Gate } from "./account";
import { DateStamp } from "./activity";
import { useShop } from "./providers";
import { ErrorState, Loading, Status } from "./ui";
import {
  CollectionFilters,
  CollectionPagination,
  useCollectionFilters,
} from "./collection-filters";

export function AffiliatePage({
  admin = false,
}: {
  admin?: boolean;
}): React.JSX.Element {
  const { user, notify } = useShop();
  const filters = useCollectionFilters();
  const client = useQueryClient();
  const [busy, setBusy] = useState<boolean>(false);
  const [adminTab, setAdminTab] = useState<"affiliates" | "referrals">("affiliates");
  const permitted: boolean = Boolean(
    user &&
      (!admin || user.is_staff || user.is_superuser || user.is_business_admin),
  );
  const workspace = useQuery({
    queryKey: ["affiliate-workspace", user?.id, filters.query],
    queryFn: () =>
      api<ReferralWorkspace>(`affiliates/workspace?${filters.query}`),
    enabled: permitted && !admin,
  });
  const operators = useQuery({
    queryKey: ["affiliate-operators", user?.id, filters.query],
    queryFn: () =>
      api<AffiliateOperatorPage>(`admin/affiliates?tab=affiliates&${filters.query}`),
    enabled: permitted && admin && adminTab === "affiliates",
  });
  const referrals = useQuery({
    queryKey: ["admin-referrals", user?.id, filters.query],
    queryFn: () =>
      api<AdminReferralPage>(`admin/affiliates?tab=referrals&${filters.query}`),
    enabled: permitted && admin && adminTab === "referrals",
  });

  const data = workspace.data;
  const error: Error | null = admin
    ? adminTab === "affiliates"
      ? operators.error
      : referrals.error
    : workspace.error;
  const isLoading: boolean = admin
    ? adminTab === "affiliates"
      ? operators.isLoading
      : referrals.isLoading
    : workspace.isLoading;

  const summary = operators.data?.summary || referrals.data?.summary;

  async function enroll(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const name = String(
      new FormData(event.currentTarget).get("name") || "",
    ).trim();
    setBusy(true);
    try {
      await api("affiliates/register", "POST", { name });
      await client.invalidateQueries({ queryKey: ["affiliate-workspace"] });
      notify("Your referral workspace is ready");
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function copyInvite(): Promise<void> {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.invite_url);
      notify("Invite link copied");
    } catch {
      notify("Copy the link from the field below", true);
    }
  }

  return (
    <Gate next={admin ? "/admin/affiliates" : "/account/affiliates"}>
      <div className="container section affiliate-workspace">
        <Link className="text-link" href={admin ? "/admin" : "/account"}>
          ← {admin ? "Backoffice" : "My account"}
        </Link>
        <h1>{admin ? "Affiliate referrals" : "Affiliates & referrals"}</h1>
        <p className="muted">
          Invite people to ProAce and track referral store credit.
        </p>
        {!permitted ? (
          <p>Backoffice access is required.</p>
        ) : (
          <>
            {isLoading && <Loading />}
            {error && <ErrorState error={error} />}

            {/* Admin Platform KPI Cards */}
            {admin && summary && (
              <div className="affiliate-summary admin-summary">
                <div>
                  <span>Total referrals</span>
                  <strong>{summary.total_referrals}</strong>
                </div>
                <div>
                  <span>Rewarded signups</span>
                  <strong>{summary.rewarded_referrals}</strong>
                </div>
                <div>
                  <span>Pending signups</span>
                  <strong>{summary.pending_referrals}</strong>
                </div>
                <div>
                  <span>Store credit awarded</span>
                  <strong>{money(summary.total_credit_awarded)}</strong>
                </div>
                <div>
                  <span>Enrolled affiliates</span>
                  <strong>{summary.total_affiliates}</strong>
                </div>
              </div>
            )}

            {/* Customer workspace overview */}
            {data && !admin && (
              <>
                <div className="affiliate-summary">
                  <div>
                    <span>Referral credit earned</span>
                    <strong>{money(data.credit_earned)}</strong>
                  </div>
                  <div>
                    <span>Rewarded signups</span>
                    <strong>
                      {data.rewarded_count} / {data.max_rewards}
                    </strong>
                  </div>
                  <div>
                    <span>Credit per rewarded signup</span>
                    <strong>{money(data.reward_amount)}</strong>
                  </div>
                </div>
                <p>
                  Earn {money(data.reward_amount)} for each of your first{" "}
                  {data.max_rewards} referred signups. Rewards are
                  non-withdrawable ProAce Wallet store credit. Additional
                  referrals are recorded without a reward.
                </p>
                <Link className="text-link" href="/account/wallet">
                  View spendable ProAce Wallet balance →
                </Link>
                {!data.enrolled ? (
                  <form className="affiliate-enrollment" onSubmit={enroll}>
                    <label className="field">
                      Affiliate display name
                      <input
                        name="name"
                        required
                        maxLength={70}
                        defaultValue={`${user?.first_name || ""} ${user?.last_name || ""}`.trim()}
                      />
                    </label>
                    <button className="button" disabled={busy}>
                      {busy ? "Joining…" : "Join referral program"}
                    </button>
                  </form>
                ) : (
                  <div className="affiliate-invite">
                    <h2>Your invite link</h2>
                    <label className="field">
                      Share this link
                      <input
                        readOnly
                        value={data.invite_url}
                        onFocus={(event) => event.currentTarget.select()}
                      />
                    </label>
                    <button
                      className="button secondary"
                      onClick={() => void copyInvite()}
                    >
                      Copy invite link
                    </button>
                    <p className="muted">
                      Referral code: <strong>{data.referral_code}</strong>
                    </p>
                  </div>
                )}
              </>
            )}

            {/* Admin Tabs */}
            {admin && (
              <div
                style={{
                  display: "flex",
                  gap: "0.75rem",
                  marginTop: "1.5rem",
                  marginBottom: "1.5rem",
                }}
              >
                <button
                  type="button"
                  className={`button ${adminTab === "affiliates" ? "" : "secondary"}`}
                  onClick={() => {
                    setAdminTab("affiliates");
                    filters.reset();
                  }}
                >
                  Enrolled affiliates ({summary?.total_affiliates ?? operators.data?.count ?? 0})
                </button>
                <button
                  type="button"
                  className={`button ${adminTab === "referrals" ? "" : "secondary"}`}
                  onClick={() => {
                    setAdminTab("referrals");
                    filters.reset();
                  }}
                >
                  Referral signups log ({summary?.total_referrals ?? referrals.data?.count ?? 0})
                </button>
              </div>
            )}

            {/* Admin: Enrolled Affiliates Tab */}
            {admin && adminTab === "affiliates" && operators.data && (
              <>
                <h2>Enrolled affiliates</h2>
                <CollectionFilters
                  filters={filters}
                  label="affiliates"
                  fields={[
                    {
                      key: "is_active",
                      label: "Account status",
                      options: [
                        { value: "true", label: "Active" },
                        { value: "false", label: "Inactive" },
                      ],
                    },
                    { key: "start_date", label: "From date", type: "date" },
                    { key: "end_date", label: "To date", type: "date" },
                  ]}
                />
                <p className="muted">
                  {operators.data.count} matching records
                </p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Affiliate</th>
                        <th>Status</th>
                        <th>Referrals / rewarded</th>
                        <th>Credit earned</th>
                        <th>Date joined</th>
                      </tr>
                    </thead>
                    <tbody>
                      {operators.data.results.map((member) => (
                        <tr key={member.id}>
                          <td>
                            <Link href={`/admin/users/${member.user}`}>
                              {member.name}
                            </Link>
                            <br />
                            {member.email}
                            <br />
                            <small className="muted">Code: {member.marketer_id}</small>
                          </td>
                          <td>
                            {member.is_active ? "Active" : "Inactive"}
                          </td>
                          <td>
                            {member.referral_count} / {member.rewarded_count}
                          </td>
                          <td>{money(member.credit_earned || "0")}</td>
                          <td>
                            <DateStamp value={member.created} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {operators.data.count === 0 && (
                  <p>
                    {filters.active
                      ? "No results match these filters. Reset filters to see all records."
                      : "No affiliates have enrolled yet."}
                  </p>
                )}
                <CollectionPagination
                  filters={filters}
                  count={operators.data.count || 0}
                />
              </>
            )}

            {/* Admin: Referral Signups Log Tab */}
            {admin && adminTab === "referrals" && referrals.data && (
              <>
                <h2>Referral signups log</h2>
                <CollectionFilters
                  filters={filters}
                  label="referrals"
                  fields={[
                    {
                      key: "status",
                      label: "Reward status",
                      options: [
                        { value: "rewarded", label: "Rewarded" },
                        { value: "pending", label: "Pending" },
                      ],
                    },
                    { key: "start_date", label: "From date", type: "date" },
                    { key: "end_date", label: "To date", type: "date" },
                  ]}
                />
                <p className="muted">
                  {referrals.data.count} matching records
                </p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Referral ID</th>
                        <th>Referred customer</th>
                        <th>Invited by (Affiliate)</th>
                        <th>Reward status</th>
                        <th>Store credit</th>
                        <th>Registration date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {referrals.data.results.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <strong>#{item.id}</strong>
                          </td>
                          <td>
                            <Link href={`/admin/users/${item.referred_user.id}`}>
                              {`${item.referred_user.first_name} ${item.referred_user.last_name}`.trim() || item.referred_user.email}
                            </Link>
                            <br />
                            <small className="muted">{item.referred_user.email}</small>
                          </td>
                          <td>
                            <Link href={`/admin/users/${item.marketer.user_id}`}>
                              {item.marketer.name}
                            </Link>
                            <br />
                            <small className="muted">Code: {item.marketer.marketer_id}</small>
                          </td>
                          <td>
                            <Status value={item.status} />
                          </td>
                          <td>
                            {item.status === "rewarded"
                              ? money(item.reward_amount)
                              : "No credit awarded"}
                          </td>
                          <td>
                            <DateStamp value={item.created} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {referrals.data.count === 0 && (
                  <p>
                    {filters.active
                      ? "No results match these filters. Reset filters to see all records."
                      : "No referral signups recorded yet."}
                  </p>
                )}
                <CollectionPagination
                  filters={filters}
                  count={referrals.data.count || 0}
                />
              </>
            )}

            {/* Customer Referral History */}
            {!admin && data?.enrolled && (
              <>
                <h2>Referral history</h2>
                <CollectionFilters
                  filters={filters}
                  label="referrals"
                  fields={[
                    {
                      key: "status",
                      label: "Reward status",
                      options: [
                        { value: "rewarded", label: "Rewarded" },
                        { value: "pending", label: "Pending" },
                      ],
                    },
                    { key: "start_date", label: "From date", type: "date" },
                    { key: "end_date", label: "To date", type: "date" },
                  ]}
                />
                <p className="muted">
                  {data.count} matching records
                </p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Referral</th>
                        <th>Status</th>
                        <th>Store credit</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.results.map((referral) => (
                        <tr key={referral.id}>
                          <td>#{referral.id}</td>
                          <td>
                            <Status value={referral.status} />
                          </td>
                          <td>
                            {referral.status === "rewarded"
                              ? money(referral.reward_amount)
                              : "No credit awarded"}
                          </td>
                          <td>
                            <DateStamp value={referral.created} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {data.count === 0 && (
                  <p>
                    {filters.active
                      ? "No results match these filters. Reset filters to see all records."
                      : "No referrals yet. Share your invite link to get started."}
                  </p>
                )}
                <CollectionPagination
                  filters={filters}
                  count={data.count || 0}
                />
              </>
            )}
          </>
        )}
      </div>
    </Gate>
  );
}
