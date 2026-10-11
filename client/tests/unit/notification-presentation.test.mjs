import assert from 'node:assert/strict';
import test from 'node:test';
import { presentNotificationOnce } from '../../src/lib/notification-presentation.ts';

test('SSE and FCM present the same inbox identity only once per account', () => {
  const messages = [];
  const notify = title => messages.push(title);
  presentNotificationOnce(9871, 12, 'Order placed', notify);
  presentNotificationOnce(9871, '12', 'Order placed', notify);
  presentNotificationOnce(9872, 12, 'Order placed', notify);
  presentNotificationOnce(9871, 13, 'Order shipped', notify);
  assert.deepEqual(messages, ['Order placed', 'Order placed', 'Order shipped']);
});
