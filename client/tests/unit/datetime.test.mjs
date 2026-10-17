import assert from 'node:assert/strict';
import { test } from 'node:test';
import { calendarDateLabel, toLocalDateTimeInput, displayDate, displayTime, displayDateTime } from '../../src/lib/datetime.ts';

test('UTC flash deadlines round-trip through local editors across DST', () => {
  const previous = process.env.TZ;
  try {
    for (const zone of ['UTC', 'America/New_York', 'Africa/Lagos', 'Asia/Tokyo']) {
      process.env.TZ = zone;
      for (const instant of ['2026-07-08T12:30:00.000Z', '2026-12-08T12:30:00.000Z']) {
        assert.equal(new Date(toLocalDateTimeInput(instant)).toISOString(), instant);
      }
      assert.equal(calendarDateLabel('2026-10-08'), '8 Oct');
    }
    assert.equal(toLocalDateTimeInput('invalid'), '');
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});


test('display dates keep the local calendar day and omit seconds', () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = 'Africa/Lagos';
    assert.equal(displayDate('2026-10-09T23:40:44Z'), '10 Oct 2026');
    assert.equal(displayTime('2026-10-09T23:40:44Z'), '00:40');
    assert.equal(displayDateTime('2026-10-09T23:40:44Z'), '10 Oct 2026 · 00:40');
    process.env.TZ = 'America/New_York';
    assert.equal(displayDate('2026-10-10T01:00:00Z'), '9 Oct 2026');
    assert.equal(displayTime('2026-10-10T01:00:00Z'), '21:00');
    for (const value of [undefined, null, '', 'invalid']) {
      assert.equal(displayDate(value), 'Not recorded');
      assert.equal(displayTime(value), '');
      assert.equal(displayDateTime(value), 'Not recorded');
    }
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

test('scheduled store drop timestamps format and round-trip correctly', () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = 'UTC';
    const dropTime = '2026-11-15T18:00:00.000Z';
    const localInput = toLocalDateTimeInput(dropTime);
    assert.equal(localInput, '2026-11-15T18:00');
    assert.equal(new Date(localInput).toISOString(), dropTime);
    assert.equal(displayDateTime(dropTime), '15 Nov 2026 · 18:00');
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

