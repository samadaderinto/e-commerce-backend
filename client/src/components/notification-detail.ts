'use client';

import { useEffect, useRef } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Page } from '@/lib/types';
import { useShop } from './providers';

/** Resolve a notification independently of listing filters and pagination. */
export function useNotificationDetail<T>(
  parameter: string,
  endpoint: string,
  onOpen: (record: T) => void,
): () => void {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const { user, notify } = useShop();
  const identity = params.get(parameter) || '';
  const valid = /^[1-9]\d*$/.test(identity);
  const callback = useRef(onOpen);
  callback.current = onOpen;
  const handled = useRef('');
  const record = useQuery({
    queryKey: ['notification-detail', user?.id, endpoint, identity],
    queryFn: () => api<Page<T>>(
      `${endpoint}${endpoint.includes('?') ? '&' : '?'}record_id=${identity}&limit=1&offset=0`,
    ),
    enabled: Boolean(user && valid),
    retry: false,
  });

  useEffect(() => {
    if (!identity) {
      handled.current = '';
      return;
    }
    const key = `${user?.id}:${endpoint}:${identity}`;
    if (handled.current === key || !user) return;
    if (!valid || record.error || (record.isSuccess && !record.data.results.length)) {
      handled.current = key;
      notify('This record is unavailable or you no longer have access to it.', true);
    } else if (record.isSuccess && record.data.results[0]) {
      handled.current = key;
      callback.current(record.data.results[0]);
    }
  }, [identity, valid, user, endpoint, record.data, record.error, record.isSuccess, notify]);

  return () => {
    if (!identity) return;
    const next = new URLSearchParams(params.toString());
    next.delete(parameter);
    router.replace(`${pathname}${next.size ? `?${next}` : ''}`, { scroll: false });
  };
}
