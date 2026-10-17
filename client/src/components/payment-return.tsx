"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Order } from "@/lib/types";
import { Gate } from "./account";
import { useShop } from "./providers";
import { ErrorState, Loading } from "./ui";

export function PaymentReturnPage(): React.JSX.Element {
  const { user } = useShop();
  const router = useRouter();
  const search = useSearchParams();
  const sessionId = search.get("session_id");
  const [error, setError] = useState<Error | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!user?.id) return;
    if (!sessionId) {
      setError(
        new Error(
          "The payment reference is missing. Open your order history to check your purchase.",
        ),
      );
      return;
    }
    let active = true;
    void api<Order>("checkout/wallet-confirm", "POST", {
      session_id: sessionId,
    })
      .then((order) => {
        if (active) router.replace(`/orders/${order.id}?placed=true`);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason
              : new Error("Unable to confirm payment."),
          );
      });
    return () => {
      active = false;
    };
  }, [user?.id, sessionId, router, attempt]);

  return (
    <Gate
      next={`/orders/stripe-return?session_id=${encodeURIComponent(sessionId || "")}`}
    >
      <div className="container section">
        {error ? (
          <ErrorState
            error={error}
            retry={sessionId ? () => {
              setError(null);
              setAttempt(current => current + 1);
            } : undefined}
          />
        ) : <Loading />}
      </div>
    </Gate>
  );
}
