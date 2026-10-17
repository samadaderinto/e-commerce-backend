import type { QueryClient } from '@tanstack/react-query';

/** Keep the observed session query attached while clearing account data. */
export async function clearSignedInSession(client: QueryClient): Promise<void> {
  await client.cancelQueries();
  client.setQueryData(['me'], null);
  client.removeQueries({
    predicate: (query) => query.queryKey[0] !== 'me',
  });
}
