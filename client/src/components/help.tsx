'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Package,
  ShieldCheck,
  Truck,
  RotateCcw,
  WalletCards,
  Percent,
} from 'lucide-react';
import { business, contactLinks } from '@/lib/business';

export function HelpPage() {
  const faqItems: [string, string][] = [
    [
      'What do the verified store checkmarks (ticks) and badge colors mean?',
      [
        'Every approved seller on ProAce receives a verified checkmark (tick) to signal authenticity, identity verification, and customer trust. As merchants grow their sales and maintain top review ratings, their verified tick automatically upgrades:',
        '• Starter Seller (Blue Tick): Staff-verified active merchant ($0–$4,999 in sales).',
        '• Booster Seller (Silver Tick): $5,000+ in verified sales.',
        '• Accelerator Seller (Electric Purple Tick): $25,000+ in verified sales.',
        '• Power Seller (Emerald Green Tick): $100,000+ in verified sales.',
        '• Mega Seller (Flame Orange Tick): $500,000+ in verified sales.',
        '• Legendary Seller (Cosmic Ruby Flame Badge): $1,000,000+ in verified sales.',
        '• Official Partner (Gold Tick): ProAce flagship & official brand partner stores (0% platform commission).',
      ].join('\n'),
    ],
    [
      'How does a store get verified to earn the blue tick?',
      'All new stores undergo mandatory verification review by our compliance team before they can go public. To qualify, merchants must complete onboarding with verified contact details, a physical pickup address, and publishable product listings that meet our safety and quality guidelines. Once staff approves the store, the blue tick is immediately activated.',
    ],
    [
      'Can a store lose its verified tick or be blocked?',
      'Yes. Verification is tied to trust and customer satisfaction. If a store violates marketplace guidelines, sells prohibited or counterfeit goods, or accumulates excessive unresolved buyer disputes, compliance staff may suspend, block, or revoke the store’s verified badge.',
    ],
    [
      'Which delivery carriers are supported, and how does shipping work?',
      [
        `Physical products are shipped across the United States using ${business.carriers}.`,
        '• Real-time carrier postage rates (USPS, UPS, FedEx, and DHL Express) are dynamically calculated at checkout based on parcel weight, package dimensions, and destination ZIP code.',
        '• Military postal destinations (APO, FPO, DPO) are fully supported and routed exclusively via USPS Ground Advantage and Priority Mail.',
        '• Digital products are delivered electronically worldwide with $0.00 shipping fees.',
        '• Curated partner products (e.g. ClickBank listings) are fulfilled directly by the external partner vendor.',
      ].join('\n'),
    ],
    [
      'How does package tracking work?',
      'Once a seller marks your order as shipped, a carrier tracking number and direct tracking link (USPS, UPS, FedEx, or DHL) appear on your order details page. You can follow parcel transit milestones in real-time on ProAce or directly through the carrier’s tracking portal.',
    ],
    [
      'What is the return and refund policy?',
      `Physical products can be returned within ${business.returnWindowDays} calendar days of delivery. When requesting a refund from your order details page, you can choose between instant ProAce Store Credit (Wallet balance) or refund to your original payment method. Physical returns are reviewed and processed within 1–2 business days.`,
    ],
    [
      'Can an order be cancelled before it ships?',
      `Yes. Orders that have not yet been marked as shipped by the seller can be cancelled within ${business.cancellationWindowHours} hours of placement. Cancellation atomically restocks inventory and immediately refunds the entire order total back to your ProAce Wallet balance for instant re-use.`,
    ],
    [
      'Can digital downloads be refunded?',
      'Digital products (e-books, software, digital artwork, audio files) are sold as one customer entitlement, so the cart quantity is limited to one. After payment, you can return to your order details page and download the file again whenever needed. Digital products are non-refundable once delivered or downloaded; if a file is corrupted, contact customer support for a verified replacement.',
    ],
    [
      'How does the ProAce referral program work?',
      `Join from My account → Affiliates & referrals, then share your invite link. Your first ${business.referralRewardLimit} referred customers who complete a successful order earn $${business.referralRewardAmount} each in non-withdrawable ProAce Wallet store credit. ${business.referralRewardPolicy} Further referrals are recorded without rewards. View referral history and spendable balance from your account.`,
    ],
    [
      'How do Curated Partner & ClickBank affiliate listings work?',
      [
        'ProAce partners with industry-leading creators and merchants via official affiliate networks (including ClickBank) to curate top-rated physical and digital products alongside our native listings.',
        '• Partner listings feature an "Official Partner Listing" badge and a direct "Buy on Partner Site" / "Get Instant Access" button.',
        '• Partner products are purchased directly through ClickBank’s secure checkout and fulfilled by the vendor under ClickBank’s 60-day customer satisfaction guarantee.',
        '• ProAce acts as an affiliate and may earn a referral commission on qualifying purchases at zero additional cost to you.',
      ].join('\n'),
    ],
    [
      'How is sales tax calculated?',
      'Destination sales taxes are calculated automatically during checkout based on the delivery ZIP code and applicable state and municipal statutory rates. Every order creates an immutable tax audit snapshot. Digital goods and eligible tax-exempt regions are calculated according to state tax regulations.',
    ],
    [
      'How does the ProAce Wallet work?',
      'Every registered user has an integrated ProAce Wallet. When you receive refund store credit, top-up balances, or cancel an unshipped order, funds are immediately available to pay for any product across the marketplace with 1-click checkout. You can also combine your wallet balance with a credit card for split-tender checkout.',
    ],
    [
      'What payment methods do you accept?',
      `${business.paymentMethods}. For Curated Partner products, payment is processed securely through ClickBank's checkout.`,
    ],
    [
      'How do seller payouts and escrow work?',
      `${business.escrowPolicy} Once cleared, merchants can withdraw available funds across all their stores via Stripe Express or direct payout after a transparent ${business.standardCommissionPercent}% platform fee (${business.officialCommissionPercent}% for Official Partner stores).`,
    ],
    [
      'Where can I manage my orders and downloads?',
      'Sign in and navigate to My Account > My Orders. Every order includes itemized receipts, reusable download links for digital goods, live parcel tracking links, and refund request forms.',
    ],
  ];

  return (
    <div className="container help-page">
      <span className="eyebrow green">A LITTLE HELP GOES A LONG WAY</span>
      <h1>
        Good questions.<br />Clear answers.
      </h1>
      <p>
        Customer support is available {business.supportSchedule}. Email{' '}
        <a href={contactLinks.supportEmail}>{business.supportEmail}</a> or message us on{' '}
        <a href={contactLinks.whatsapp} target="_blank" rel="noreferrer">
          WhatsApp at {business.whatsapp}
        </a>.
      </p>

      <div className="help-links">
        <Link href="/account/orders">
          <Package />
          <h3>Follow your order</h3>
          <ArrowRight size={18} />
        </Link>
        <Link href="/account/wallet">
          <WalletCards />
          <h3>ProAce Wallet</h3>
          <ArrowRight size={18} />
        </Link>
        <Link href="/account/addresses">
          <Truck />
          <h3>Delivery addresses</h3>
          <ArrowRight size={18} />
        </Link>
      </div>

      <h2>The everyday questions</h2>
      {faqItems.map(([question, answer]) => (
        <details key={question}>
          <summary>{question}</summary>
          <p style={{ whiteSpace: 'pre-line' }}>{answer}</p>
        </details>
      ))}

      <p style={{ marginTop: '2.5rem' }}>
        Order & refund questions: <a href={contactLinks.orderEmail}>{business.orderEmail}</a>
        <br />
        Seller support & payouts: <a href={contactLinks.sellerEmail}>{business.sellerEmail}</a>
      </p>
      <Link className="text-link" href="/shop">
        Back to discovering <ArrowRight size={16} />
      </Link>
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
            {business.legalName} stores the account details you provide, including your name,
            email and phone number. Delivery addresses, ProAce Wallet balances, and orders are
            associated with your account. Passwords are encrypted as secure salted PBKDF2/Argon2 hashes.
          </p>
          <h2>Cookies, sessions and authentication</h2>
          <p>
            Essential secure, SameSite HTTP-only cookies keep you signed in without exposing tokens
            to third-party scripts. Your browser stores guest shopping bags and saved items locally,
            and signing in automatically merges eligible items with your account.
          </p>
          <h2>Order fulfillment and carrier sharing</h2>
          <p>
            When an order is placed, order details and delivery addresses are shared with the specific
            seller and chosen delivery carrier ({business.carriers}) solely for fulfillment and tracking.
            Payment processors handle transactions under strict PCI-DSS standards.
          </p>
          <h2>Affiliate partner links & ClickBank tracking</h2>
          <p>
            When you view or click on Curated Partner listings, outbound requests route through our secure
            tracking proxy to append HopLink referral tags. External transactions take place entirely on
            ClickBank’s platform under ClickBank’s privacy policy.
          </p>
          <h2>Your choices</h2>
          <p>
            You can update your personal details, remove saved delivery addresses, and manage your account
            at any time through your Account portal. For privacy inquiries or data requests, email{' '}
            <a href={`mailto:${business.privacyEmail}`}>{business.privacyEmail}</a>.
          </p>
        </>
      ) : (
        <>
          <h2>Service Area & Multi-Carrier Delivery</h2>
          <p>
            {business.legalName} serves customers across the United States for physical goods via{' '}
            {business.carriers}. Shipping rates are dynamically calculated based on parcel weight, package
            dimensions, and destination ZIP code. Military APO/FPO/DPO addresses are supported exclusively
            via USPS. Digital products are delivered electronically worldwide with $0.00 shipping fees.
          </p>
          <h2>Destination Sales Taxes</h2>
          <p>
            Sales taxes are computed based on destination delivery addresses using local statutory tax rules
            and ZIP-code overrides. Every completed transaction generates an immutable tax snapshot for regulatory
            compliance.
          </p>
          <h2>Store Verification & Verified Tick Badges</h2>
          <p>
            To protect buyers and ensure marketplace authenticity, all seller stores undergo mandatory onboarding
            compliance review by ProAce staff before going public. Once approved, sellers receive the{' '}
            <strong>Verified Blue Tick</strong>. Sellers automatically unlock progressive tier checkmarks
            (Silver, Purple, Emerald, Flame Orange, Cosmic Ruby, and Gold) based on cumulative verified sales and top customer reviews.
            Official Partner flagship stores operate with Gold Ticks and 0% platform commission. Badges remain subject
            to ongoing quality and safety audits.
          </p>
          <h2>{business.returnWindowDays}-Day Return Window & Refunds</h2>
          <p>
            Customers may request a return or refund for physical items within{' '}
            <strong>{business.returnWindowDays} calendar days of delivery</strong>. Approved refunds can be credited
            instantly to your <strong>ProAce Wallet (Store Credit)</strong> or refunded to the original payment method.
            Physical returns are inspected and resolved within 1–2 business days.
          </p>
          <h2>{business.cancellationWindowHours}-Hour Order Cancellation</h2>
          <p>
            Orders that have not yet been marked as shipped by the seller can be cancelled within{' '}
            <strong>{business.cancellationWindowHours} hours of placement</strong>. Cancellation automatically
            restocks inventory and immediately refunds the entire transaction amount to your ProAce Wallet.
          </p>
          <h2>Digital Products Policy</h2>
          <p>
            Digital goods (software, ebooks, media files) are delivered immediately upon order confirmation.
            Each purchase grants one customer entitlement; repeat downloads are available at any time from your completed
            order details page. Digital products are non-refundable once delivered or downloaded, except that customer
            support may provide a verified replacement for a corrupted or inaccessible file.
          </p>
          <h2>Curated Partner & ClickBank Affiliate Disclosure</h2>
          <p>
            ProAce features select curated partner products from verified external vendors through the{' '}
            {business.affiliateNetwork}. When you click a partner listing, checkout and payment take place directly on
            ClickBank’s secure checkout, and fulfillment is handled by the partner vendor under ClickBank’s 60-day customer
            satisfaction guarantee. Pursuant to FTC guidelines, ProAce discloses that we may receive an affiliate referral
            commission on eligible purchases made through these links at zero additional cost to the buyer.
          </p>
          <h2>Merchant Escrow & Platform Commission</h2>
          <p>
            Standard merchants receive 96% of net sales after a transparent {business.standardCommissionPercent}% platform
            fee (Official Partner stores retain 100% of sales with {business.officialCommissionPercent}% commission). Net
            earnings remain protected by buyer review escrow. {business.escrowPolicy}
          </p>
          <h2>Payment Methods</h2>
          <p>
            Native marketplace orders accept {business.paymentMethods}. Partner products are purchased through
            ClickBank’s checkout system.
          </p>
          <h2>Questions</h2>
          <p>
            Email <a href={contactLinks.orderEmail}>{business.orderEmail}</a> for order assistance or{' '}
            <a href={`mailto:${business.legalEmail}`}>{business.legalEmail}</a> for legal and compliance inquiries.
          </p>
        </>
      )}
      <Link className="text-link" href="/help">
        Visit the help centre <ArrowRight size={16} />
      </Link>
    </article>
  );
}
