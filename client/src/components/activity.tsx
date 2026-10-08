import React from 'react';

export function activityDate(value?: string | null): string {
  if (!value) return 'Not recorded';
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? new Date(value).toLocaleString() : 'Not recorded';
}

type ActivityDetailsProps = {
  updated?: string;
  last_login?: string | null;
  last_active_at?: string | null;
};

export function ActivityDetails({
  updated,
  last_login,
  last_active_at,
}: ActivityDetailsProps): React.JSX.Element {
  return (
    <dl className="muted">
      <dt>Last active</dt>
      <dd>{activityDate(last_active_at)}</dd>
      <dt>Last login</dt>
      <dd>{activityDate(last_login)}</dd>
      <dt>Profile updated</dt>
      <dd>{activityDate(updated)}</dd>
    </dl>
  );
}
