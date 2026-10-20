export const business = {
  publicName: 'ProAce International Consulting and Conglomerate',
  legalName: 'ProAce International Consulting and Conglomerate',
  location: 'Tampa, Florida, United States',
  mainPhone: '301-325-150',
  whatsapp: '+1 301 325 1550',
  generalEmail: 'admin@proaceintl.com',
  supportEmail: 'admin@proaceintl.com',
  orderEmail: 'productace@proaceintl.com',
  sellerEmail: 'admin@proaceintl.com',
  privacyEmail: 'admin@proaceintl.com',
  legalEmail: 'admin@proaceintl.com',
  supportSchedule: 'Monday–Sunday, 9:00 AM–5:00 PM Eastern Time',
  serviceArea: 'United States for physical products; worldwide for digital downloads',
  paymentMethods:
    'Major credit and debit cards (Visa, Mastercard, Amex, Discover), Apple Pay and Google Pay via Stripe, and ProAce Wallet balance',
  carriers:
    'USPS, UPS, FedEx, and DHL Express (USPS required for military APO/FPO/DPO addresses)',
  returnWindowDays: 7,
  cancellationWindowHours: 12,
  escrowReviewDays: 7,
  escrowPolicy: 'Physical sales remain in review until seven days after the store shipment’s recorded delivery, and never clear before the original seven-day sale hold. Undelivered physical sales stay in review. Digital sales retain the seven-day sale hold.',
  standardCommissionPercent: 4,
  officialCommissionPercent: 0,
  referralRewardAmount: 25,
  referralRewardLimit: 4,
  referralRewardPolicy: 'Referral rewards require a fully paid qualifying order and are reversed when that order is cancelled or refunded. Already-spent promotional credit is recovered from the wallet balance, which can remain negative until replenished.',
  affiliateNetwork: 'ClickBank Official Partner Network',
} as const;

export const contactLinks = {
  generalEmail: `mailto:${business.generalEmail}`,
  supportEmail: `mailto:${business.supportEmail}`,
  orderEmail: `mailto:${business.orderEmail}`,
  sellerEmail: `mailto:${business.sellerEmail}`,
  whatsapp: `https://wa.me/${business.whatsapp.replace(/\D/g, '')}`,
} as const;
