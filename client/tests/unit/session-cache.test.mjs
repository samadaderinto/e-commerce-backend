import assert from 'node:assert/strict';
import test from 'node:test';
import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { clearSignedInSession } from '../../src/lib/session-cache.ts';

test('logout updates the existing session observer and rejects a late profile response', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const previous = { id: 206, first_name: 'Kingsley' };
  client.setQueryData(['me'], previous);
  client.setQueryData(['orders', 206], [{ id: 1 }]);
  let complete;
  const pending = new Promise(resolve => { complete = resolve; });
  const observer = new QueryObserver(client, {
    queryKey: ['me'],
    queryFn: () => pending,
    staleTime: Infinity,
  });
  const observed = [];
  const unsubscribe = observer.subscribe(result => observed.push(result.data));
  const fetching = observer.refetch();
  await clearSignedInSession(client);
  complete(previous);
  await fetching;
  assert.equal(observer.getCurrentResult().data, null);
  assert.equal(client.getQueryData(['me']), null);
  assert.equal(client.getQueryData(['orders', 206]), undefined);
  assert.ok(observed.includes(null));
  unsubscribe();
  client.clear();
});
