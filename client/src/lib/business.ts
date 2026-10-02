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
  serviceArea: 'International',
  paymentMethods: 'PayPal, Cash App, major credit cards and Stripe',
} as const;

export const contactLinks = {
  generalEmail: `mailto:${business.generalEmail}`,
  supportEmail: `mailto:${business.supportEmail}`,
  orderEmail: `mailto:${business.orderEmail}`,
  sellerEmail: `mailto:${business.sellerEmail}`,
  whatsapp: `https://wa.me/${business.whatsapp.replace(/\D/g, '')}`,
} as const;
