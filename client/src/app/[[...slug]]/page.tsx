import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import { HomePage, ProductPage, SavedPage, ShopPage } from '@/components/storefront';
import { AccountPage, AuthPage, OrderPage } from '@/components/account';
import { CartPage, CheckoutPage } from '@/components/cart';
import { MerchantPage } from '@/components/merchant';
import { HelpPage, PolicyPage } from '@/components/help';
import { Loading } from '@/components/ui';
import { AdminDashboardPage, AdminStaffPage } from '@/components/admin';

export default async function Page({ params }: { params: Promise<{slug?: string[]}> }) {
  const { slug = [] } = await params;
  let content;
  if (!slug.length) content = <HomePage />;
  else if (slug[0] === 'shop' && slug.length === 1) content = <ShopPage />;
  else if (slug[0] === 'products' && /^\d+$/.test(slug[1] || '') && slug.length === 2) content = <ProductPage id={slug[1]} key={slug[1]} />;
  else if (slug[0] === 'cart' && slug.length === 1) content = <CartPage />;
  else if (slug[0] === 'checkout' && slug.length === 1) content = <CheckoutPage />;
  else if (slug[0] === 'saved' && slug.length === 1) content = <SavedPage />;
  else if (['login', 'register', 'forgot-password', 'reset-password', 'verify-email'].includes(slug[0]) && slug.length === 1) content = <AuthPage mode={slug[0]} key={slug[0]} />;
  else if (slug[0] === 'account' && slug.length <= 2 && (!slug[1] || ['orders', 'addresses', 'profile'].includes(slug[1]))) content = <AccountPage section={slug[1]} />;
  else if (slug[0] === 'orders' && /^\d+$/.test(slug[1] || '') && slug.length === 2) content = <OrderPage id={slug[1]} />;
  else if (slug[0] === 'merchant' && slug.length <= 3 && (!slug[1] || ['products', 'orders', 'settings', 'new-store'].includes(slug[1])) && (!slug[2] || (slug[1] === 'products' && (slug[2] === 'new' || /^\d+$/.test(slug[2]))))) content = <MerchantPage segments={slug.slice(1)} />;
  else if (slug[0] === 'admin' && slug.length === 1) content = <AdminDashboardPage />;
  else if (slug[0] === 'admin' && slug[1] === 'staff' && slug.length === 2) content = <AdminStaffPage />;
  else if (slug[0] === 'help' && slug.length === 1) content = <HelpPage />;
  else if (['privacy', 'terms'].includes(slug[0]) && slug.length === 1) content = <PolicyPage type={slug[0]} />;
  else notFound();
  return <Suspense fallback={<Loading />}>{content}</Suspense>;
}
