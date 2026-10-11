import React from 'react';

import { displayDate, displayTime, displayDateTime } from '@/lib/datetime';

export function activityDate(value?: string | null): string {
  return displayDateTime(value);
}

type DateStampProps = {
  value?: string | null;
  label?: string;
  dateOnly?: boolean;
};

export function DateStamp({
  value,
  label,
  dateOnly = false,
}: DateStampProps): React.JSX.Element {
  const date: string = displayDate(value);
  const time: string = dateOnly ? '' : displayTime(value);
  return (
    <span className="date-stamp">
      {label && <span className="date-stamp-label">{label}</span>}
      {date === 'Not recorded' ? (
        <span className="date-stamp-missing">{date}</span>
      ) : (
        <time
          className="date-stamp-value"
          dateTime={value ?? undefined}
          title={displayDateTime(value)}
        >
          <span className="date-stamp-day">{date}</span>
          {time && <span className="date-stamp-time">{time}</span>}
        </time>
      )}
    </span>
  );
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
    <dl className="activity-details" aria-label="Account activity">
      <div className="activity-detail">
        <dt>Last active</dt>
        <dd>
          <DateStamp value={last_active_at} />
        </dd>
      </div>
      <div className="activity-detail">
        <dt>Last login</dt>
        <dd>
          <DateStamp value={last_login} />
        </dd>
      </div>
      <div className="activity-detail">
        <dt>Profile updated</dt>
        <dd>
          <DateStamp value={updated} />
        </dd>
      </div>
    </dl>
  );
}
