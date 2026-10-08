import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import { MandatoryPasswordChange } from '@/components/shell';
import {
  HomePage,
  ProductPage,
  SavedPage,
  ShopPage,
} from '@/components/storefront';
import {
  AccountPage,
  AuthPage,
  OrderPage,
} from '@/components/account';
import {
  CartPage,
  CheckoutPage,
} from '@/components/cart';
import {
  MerchantPage,
  ProductPreviewPage,
} from '@/components/merchant';
import {
  HelpPage,
  PolicyPage,
} from '@/components/help';
import { AppearanceSettings } from '@/components/theme';
import { Loading } from '@/components/ui';
import {
  AdminStoresPage,
  AdminStoreDetailPage,
  AdminDashboardPage,
  AdminStaffPage,
  AdminUsersPage,
  AdminUserDetailPage,
  AdminOrdersPage,
  AdminCouponsPage,
  AdminTaxesPage,
  AdminRefundsPage,
  AdminCommissionPage,
  AdminPayoutsPage,
} from '@/components/admin';
import { NotificationsPage } from '@/components/notifications';

export default async function Page({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { slug = [] } = await params;
  let content;

  if (slug[0] === 'change-password' && slug.length === 1) {
    content = <MandatoryPasswordChange />;
  } else if (!slug.length) {
    content = <HomePage />;
  } else if (slug[0] === 'shop' && slug.length === 1) {
    content = <ShopPage />;
  } else if (slug[0] === 'merchant' && slug[1] === 'products' && slug[2] === 'preview' && slug.length === 3) {
    content = <ProductPreviewPage />;
  } else if (slug[0] === 'products' && /^\d+$/.test(slug[1] || '') && slug.length === 2) {
    content = <ProductPage id={slug[1]} key={slug[1]} />;
  } else if (slug[0] === 'settings' && slug.length === 1) {
    content = (
      <div className="container section app-settings">
        <h1>App settings</h1>
        <AppearanceSettings />
      </div>
    );
  } else if (slug[0] === 'cart' && slug.length === 1) {
    content = <CartPage />;
  } else if (slug[0] === 'checkout' && slug.length === 1) {
    content = <CheckoutPage />;
  } else if (slug[0] === 'saved' && slug.length === 1) {
    content = <SavedPage />;
  } else if (
    ['login', 'register', 'forgot-password', 'reset-password', 'verify-email'].includes(slug[0]) &&
    slug.length === 1
  ) {
    content = <AuthPage mode={slug[0]} key={slug[0]} />;
  } else if (slug[0] === 'notifications' && slug.length === 1) {
    content = <NotificationsPage />;
  } else if (
    slug[0] === 'account' &&
    slug.length <= 2 &&
    (!slug[1] || ['orders', 'wallet', 'addresses', 'profile'].includes(slug[1]))
  ) {
    content = <AccountPage section={slug[1]} />;
  } else if (slug[0] === 'orders' && /^\d+$/.test(slug[1] || '') && slug.length === 2) {
    content = <OrderPage id={slug[1]} />;
  } else if (
    slug[0] === 'merchant' &&
    slug.length <= 3 &&
    (!slug[1] || ['products', 'orders', 'payments', 'notifications', 'settings', 'new-store'].includes(slug[1])) &&
    (!slug[2] || (slug[1] === 'products' && (slug[2] === 'new' || /^\d+$/.test(slug[2]))))
  ) {
    content = <MerchantPage segments={slug.slice(1)} />;
  } else if (slug[0] === 'admin' && slug.length === 1) {
    content = <AdminDashboardPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'orders' && slug.length === 2) {
    content = <AdminOrdersPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'payouts' && slug.length === 2) {
    content = <AdminPayoutsPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'coupons' && slug.length === 2) {
    content = <AdminCouponsPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'taxes' && slug.length === 2) {
    content = <AdminTaxesPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'refunds' && slug.length === 2) {
    content = <AdminRefundsPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'stores' && slug.length === 2) {
    content = <AdminStoresPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'stores' && /^\d+$/.test(slug[2] || '') && slug.length === 3) {
    content = <AdminStoreDetailPage id={slug[2]} />;
  } else if (slug[0] === 'admin' && slug[1] === 'staff' && slug.length === 2) {
    content = <AdminStaffPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'users' && slug.length === 2) {
    content = <AdminUsersPage />;
  } else if (slug[0] === 'admin' && slug[1] === 'users' && /^\d+$/.test(slug[2] || '') && slug.length === 3) {
    content = <AdminUserDetailPage id={slug[2]} />;
  } else if (slug[0] === 'admin' && slug[1] === 'commission' && slug.length === 2) {
    content = <AdminCommissionPage />;
  } else if (slug[0] === 'stores' && /^\d+$/.test(slug[1] || '') && slug.length === 2) {
    content = <ShopPage />;
  } else if (slug[0] === 'help' && slug.length === 1) {
    content = <HelpPage />;
  } else if (['privacy', 'terms'].includes(slug[0]) && slug.length === 1) {
    content = <PolicyPage type={slug[0]} />;
  } else {
    notFound();
  }

  return <Suspense fallback={<Loading />}>{content}</Suspense>;
}
