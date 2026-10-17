import assert from 'node:assert/strict';
import test from 'node:test';
import { notificationAction } from '../../src/lib/notification-action.ts';

test('notification actions cover record types with contextual labels', () => {
  for (const [category, url, label] of [
    ['order', '/admin/orders?order=8', 'View order'],
    ['refund', '/admin/refunds?refund=4', 'View refund'],
    ['refund', '/merchant/refunds?store=2&refund=4', 'View refund'],
    ['payout', '/merchant/payments?store=2&payout=6', 'View payout'],
    ['wallet', '/account/wallet', 'View wallet'],
    ['store', '/admin/stores/7', 'View store'],
    ['account', '/account/profile', 'View account'],
  ]) {
    assert.deepEqual(notificationAction({ category, data: { url } }), { href: url, label });
  }
});

test('notification actions reject external, ambiguous and self-loop destinations', () => {
  for (const url of ['https://evil.test', '//evil.test', '/\\evil.test', '/ notifications', '/notifications', null]) {
    assert.equal(notificationAction({ data: { url } }), null);
  }
  assert.equal(notificationAction({ data: null }), null);
});
