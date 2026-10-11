import React from 'react';
import { Check, Clock, RotateCcw, XCircle } from 'lucide-react';

import { DateStamp } from './activity';

type OrderStatusTrackerProps = {
  status: string;
  isDigital: boolean;
  changedAt?: string | null;
};

type OrderStep = { status: string; label: string };

const labels: Record<string, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  shipped: 'Shipped',
  delivered: 'Delivered',
  'picked up': 'Picked up',
  cancelled: 'Cancelled',
  refunded: 'Refunded',
};

export function OrderStatusTracker({
  status,
  isDigital,
  changedAt,
}: OrderStatusTrackerProps): React.JSX.Element {
  const terminal: boolean = status === 'cancelled' || status === 'refunded';
  const steps: OrderStep[] = [
    { status: 'pending', label: 'Pending' },
    { status: 'confirmed', label: 'Confirmed' },
    ...(status === 'picked up'
      ? [{ status: 'picked up', label: 'Picked up' }]
      : [
          ...(!isDigital ? [{ status: 'shipped', label: 'Shipped' }] : []),
          { status: 'delivered', label: 'Delivered' },
        ]),
  ];
  const currentIndex: number = steps.findIndex(step => step.status === status);

  if (terminal || currentIndex < 0) {
    return (
      <section className="order-state-notice" role="status" aria-label="Order status">
        {status === 'cancelled' ? (
          <XCircle size={24} aria-hidden="true" />
        ) : status === 'refunded' ? (
          <RotateCcw size={24} aria-hidden="true" />
        ) : (
          <Clock size={24} aria-hidden="true" />
        )}
        <div>
          <strong>{labels[status] ?? status}</strong>
          {status === 'cancelled' && <p>This order has been cancelled and will not proceed to fulfillment.</p>}
          {status === 'refunded' && <p>This order has been refunded. See the payment and refund details below.</p>}
          {changedAt && <DateStamp value={changedAt} />}
        </div>
      </section>
    );
  }

  return (
    <div className="order-progress" role="list" aria-label="Order status tracker">
      {steps.map((step, index) => {
        const isDone: boolean = currentIndex >= index;
        const isCurrent: boolean = currentIndex === index;
        const className: string = [
          isDone ? 'done' : '',
          isCurrent ? 'current' : '',
          currentIndex > index ? 'line-done' : '',
        ].filter(Boolean).join(' ');
        return (
          <div
            key={step.status}
            className={className}
            role="listitem"
            aria-current={isCurrent ? 'step' : undefined}
          >
            <span aria-hidden="true">
              {isCurrent && status === 'pending' ? (
                <Clock size={14} />
              ) : isDone ? (
                <Check size={14} strokeWidth={2.5} />
              ) : (
                <span className="step-dot" />
              )}
            </span>
            <strong>{step.label}</strong>
          </div>
        );
      })}
    </div>
  );
}
