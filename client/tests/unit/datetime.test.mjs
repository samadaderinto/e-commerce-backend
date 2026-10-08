import assert from 'node:assert/strict';
import { test } from 'node:test';
import { calendarDateLabel, toLocalDateTimeInput } from '../../src/lib/datetime.ts';

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
