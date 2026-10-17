"use client";

import { Field } from "./ui";

export type PayoutAccountSort = "recent" | "name";

type PayoutAccountFiltersProps = {
  search: string;
  onSearch: (value: string) => void;
  defaultOnly: boolean;
  onDefaultOnly: (value: boolean) => void;
  sort: PayoutAccountSort;
  onSort: (value: PayoutAccountSort) => void;
  placeholder: string;
  count: number;
  total: number;
};

export function PayoutAccountFilters(props: PayoutAccountFiltersProps): React.JSX.Element {
  const active = Boolean(props.search.trim() || props.defaultOnly || props.sort !== "recent");
  return (
    <div className="payout-account-filters">
      <div className="payout-account-filter-controls">
        <Field label="Search accounts">
          <input
            type="search"
            placeholder={props.placeholder}
            value={props.search}
            onChange={event => props.onSearch(event.target.value)}
          />
        </Field>
        <Field label="Account preference">
          <select value={props.defaultOnly ? "default" : "all"} onChange={event => props.onDefaultOnly(event.target.value === "default")}>
            <option value="all">All accounts</option>
            <option value="default">Default only</option>
          </select>
        </Field>
        <Field label="Sort accounts">
          <select value={props.sort} onChange={event => props.onSort(event.target.value as PayoutAccountSort)}>
            <option value="recent">Recently saved</option>
            <option value="name">Name A–Z</option>
          </select>
        </Field>
      </div>
      <div className="payout-account-filter-summary">
        <span aria-live="polite">{props.count} of {props.total} accounts</span>
        {active && (
          <button type="button" className="text-button" onClick={() => {
            props.onSearch("");
            props.onDefaultOnly(false);
            props.onSort("recent");
          }}>Clear filters</button>
        )}
      </div>
    </div>
  );
}
