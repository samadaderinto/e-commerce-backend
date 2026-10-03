'use client';
import Link from 'next/link';
import { ArrowRight, Package, ShieldCheck, Truck } from 'lucide-react';
import { business, contactLinks } from '@/lib/business';
export function HelpPage() {
  return (
    <div className="container help-page">
      <span className="eyebrow green">A LITTLE HELP GOES A LONG WAY</span>
      <h1>Good questions.<br />Clear answers.</h1>
      <p>
        Customer support is available {business.supportSchedule}. Email{' '}
        <a href={contactLinks.supportEmail}>{business.supportEmail}</a> or message us on{' '}
        <a href={contactLinks.whatsapp} target="_blank" rel="noreferrer">
          WhatsApp at {business.whatsapp}
        </a>.
      </p>

      <div className="help-links">
        <Link href="/account/orders"><Package /><h3>Follow your order</h3><ArrowRight size={18} /></Link>
        <Link href="/account/wallet"><ShieldCheck /><h3>ProAce Wallet</h3><ArrowRight size={18} /></Link>
        <Link href="/account/addresses"><Truck /><h3>Delivery addresses</h3><ArrowRight size={18} /></Link>
      </div>

      <h2>The everyday questions</h2>
      {[
        [
          'How does package tracking work?',
          'Once a seller ships your order, a tracking number and direct USPS tracking link appear on your order details page. You can follow parcel transit milestones in real-time on ProAce or directly on USPS.com.',
        ],
        [
          'What is the return and refund policy?',
          'Physical products can be returned within 7 days of order placement. When requesting a refund from your order page, you can choose between instant ProAce Store Credit (Wallet balance) or refund to your original payment method. Physical returns are reviewed and processed within 1–2 business days.',
        ],
        [
          'Can digital downloads be refunded?',
          'Digital products (e-books, software, digital artwork) are non-refundable once delivered or downloaded. If you experience technical difficulties with a downloaded file, please contact support for immediate assistance.',
        ],
        [
          'How does the ProAce Wallet work?',
          'Every registered user has an integrated ProAce Wallet. When you receive refund store credit or top-up balances, funds are immediately available to pay for any product across the marketplace with 1-click checkout.',
        ],
        [
          'How much is delivery?',
          'Digital products have no shipping fees and are delivered worldwide instantly. Physical products are delivered via USPS across the United States, with postage calculated automatically based on parcel weight and destination ZIP code.',
        ],
        [
          'How do I pay?',
          `We accept ${business.paymentMethods}, as well as direct payments using your ProAce Wallet balance.`,
        ],
        [
          'How do seller payouts and escrow work?',
          'Net sales from new orders are held in a 7-day buyer review escrow corresponding to the refund window. Once cleared, merchants can withdraw available funds to their bank accounts or payment accounts after a transparent 4% platform fee.',
        ],
        [
          'Where can I manage my orders?',
          'Sign in and navigate to My Account > My Orders. Every order includes itemized receipts, download links for digital goods, live USPS tracking, and return request forms.',
        ],
      ].map(([question, answer]) => (
        <details key={question}>
          <summary>{question}</summary>
          <p>{answer}</p>
        </details>
      ))}

      <p style={{ marginTop: '2.5rem' }}>
        Order & refund questions: <a href={contactLinks.orderEmail}>{business.orderEmail}</a><br />
        Seller support & payouts: <a href={contactLinks.sellerEmail}>{business.sellerEmail}</a>
      </p>
      <Link className="text-link" href="/shop">Back to discovering <ArrowRight size={16} /></Link>
    </div>
  );
}

export function PolicyPage({ type }: { type: string }) {
  const privacy = type === 'privacy';
  return (
    <article className="container policy-page">
      <span className="eyebrow green">GOOD TO KNOW</span>
      <h1>{privacy ? 'Your privacy matters.' : 'Shopping & Returns Terms.'}</h1>
      {privacy ? (
        <>
          <h2>Your account information</h2>
          <p>
            {business.legalName} stores the account details you provide, including your name, email and phone number. Delivery addresses, ProAce Wallet balances, and orders are associated with your account. Passwords are stored as secure salted PBKDF2/Argon2 hashes.
          </p>
          <h2>Cookies and saved finds</h2>
          <p>
            Essential secure cookies keep you signed in. Your browser stores guest shopping bags and saved items locally. Signing in automatically merges eligible guest items to your account.
          </p>
          <h2>Orders, sellers and processors</h2>
          <p>
            Order details and delivery addresses are shared with the specific seller for fulfillment. Payment processors handle transactions under strict PCI-DSS standards.
          </p>
          <h2>Your choices</h2>
          <p>
            You can update your personal details, remove saved addresses, and manage your account at any time. For privacy inquiries, email{' '}
            <a href={`mailto:${business.privacyEmail}`}>{business.privacyEmail}</a>.
          </p>
        </>
      ) : (
        <>
          <h2>Service Area & Delivery</h2>
          <p>
            {business.legalName} serves customers across the United States for physical goods via USPS postage calculation. Digital products are delivered electronically worldwide with zero shipping fees.
          </p>
          <h2>7-Day Return Window & Refunds</h2>
          <p>
            Customers may request a return or refund for physical items within <strong>7 calendar days</strong> of placing their order. Approved refunds can be credited instantly to your <strong>ProAce Wallet (Store Credit)</strong> or refunded to the original payment method. Physical returns are inspected and resolved within 1–2 business days.
          </p>
          <h2>Digital Products Policy</h2>
          <p>
            Digital goods (software, documents, media downloads) are delivered immediately upon order confirmation and are non-refundable once downloaded. If a file is corrupted, support will provide a verified replacement.
          </p>
          <h2>Merchant Escrow & Platform Fees</h2>
          <p>
            Merchants receive 96% of net sales after a standard 4% platform processing fee. Net earnings from orders are held in 7-day buyer escrow before clearing into available payout balances.
          </p>
          <h2>Order Cancellation</h2>
          <p>
            Orders that have not yet been marked as shipped by the merchant can be cancelled within 12 hours of order placement.
          </p>
          <h2>Questions</h2>
          <p>
            Email <a href={contactLinks.orderEmail}>{business.orderEmail}</a> for order assistance or{' '}
            <a href={`mailto:${business.legalEmail}`}>{business.legalEmail}</a> for legal questions.
          </p>
        </>
      )}
      <Link className="text-link" href="/help">Visit the help centre <ArrowRight size={16} /></Link>
    </article>
  );
}
