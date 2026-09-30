'use client';
import { ErrorState } from '@/components/ui';
export default function Error({ reset }: { reset: () => void }) { return <ErrorState error={new globalThis.Error('We couldn’t load this page. Please try again.')} retry={reset} />; }
