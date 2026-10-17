'use client';

import dynamic from 'next/dynamic';

// Keep this boundary client-side so only the rendered feature bundle is loaded.
// SSR stays enabled; route resolution and redirects remain on the server.
export const HomePage = dynamic(() =>
  import('./storefront').then(module => module.HomePage),
);
export const ShopPage = dynamic(() =>
  import('./storefront').then(module => module.ShopPage),
);
export const ProductPage = dynamic(() =>
  import('./storefront').then(module => module.ProductPage),
);
export const SavedPage = dynamic(() =>
  import('./storefront').then(module => module.SavedPage),
);
export const AccountPage = dynamic(() =>
  import('./account').then(module => module.AccountPage),
);
export const AuthPage = dynamic(() =>
  import('./account').then(module => module.AuthPage),
);
export const OrderPage = dynamic(() =>
  import('./account').then(module => module.OrderPage),
);
export const CartPage = dynamic(() =>
  import('./cart').then(module => module.CartPage),
);
export const CheckoutPage = dynamic(() =>
  import('./cart').then(module => module.CheckoutPage),
);
export const MerchantPage = dynamic(() =>
  import('./merchant').then(module => module.MerchantPage),
);
export const ProductPreviewPage = dynamic(() =>
  import('./merchant').then(module => module.ProductPreviewPage),
);
export const HelpPage = dynamic(() =>
  import('./help').then(module => module.HelpPage),
);
export const PolicyPage = dynamic(() =>
  import('./help').then(module => module.PolicyPage),
);
export const ConnectedAccountSettings = dynamic(() =>
  import('./connected-accounts').then(module => module.ConnectedAccountSettings),
);
export const AffiliatePage = dynamic(() =>
  import('./affiliates').then(module => module.AffiliatePage),
);
export const PaymentReturnPage = dynamic(() =>
  import('./payment-return').then(module => module.PaymentReturnPage),
);
export const NotificationsPage = dynamic(() =>
  import('./notifications').then(module => module.NotificationsPage),
);
export const AdminStoresPage = dynamic(() =>
  import('./admin').then(module => module.AdminStoresPage),
);
export const AdminStoreDetailPage = dynamic(() =>
  import('./admin').then(module => module.AdminStoreDetailPage),
);
export const AdminDashboardPage = dynamic(() =>
  import('./admin').then(module => module.AdminDashboardPage),
);
export const AdminStaffPage = dynamic(() =>
  import('./admin').then(module => module.AdminStaffPage),
);
export const AdminUsersPage = dynamic(() =>
  import('./admin').then(module => module.AdminUsersPage),
);
export const AdminUserDetailPage = dynamic(() =>
  import('./admin').then(module => module.AdminUserDetailPage),
);
export const AdminOrdersPage = dynamic(() =>
  import('./admin').then(module => module.AdminOrdersPage),
);
export const AdminCouponsPage = dynamic(() =>
  import('./admin').then(module => module.AdminCouponsPage),
);
export const AdminTaxesPage = dynamic(() =>
  import('./admin').then(module => module.AdminTaxesPage),
);
export const AdminRefundsPage = dynamic(() =>
  import('./admin').then(module => module.AdminRefundsPage),
);
export const AdminCommissionPage = dynamic(() =>
  import('./admin').then(module => module.AdminCommissionPage),
);
export const AdminPayoutsPage = dynamic(() =>
  import('./admin').then(module => module.AdminPayoutsPage),
);
