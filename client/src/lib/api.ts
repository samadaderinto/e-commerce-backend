export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
function message(data: unknown): string {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(message).join(' ');
  if (data && typeof data === 'object') return Object.entries(data).map(([key, value]) => `${key === 'detail' ? '' : `${key.replaceAll('_', ' ')}: `}${message(value)}`).join(' ');
  return 'Something went wrong. Please try again.';
}
export async function api<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  const multipart = data instanceof FormData;
  const response = await fetch(`/api/${path}`, { method, credentials: 'same-origin', headers: data && !multipart ? { 'Content-Type': 'application/json' } : undefined, body: data ? multipart ? data : JSON.stringify(data) : undefined });
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(message(result), response.status);
  return result as T;
}
export const money = (value: string | number) => new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 }).format(Number(value));
export const categories = [
  { key: 'electronics', name: 'Electronics' }, { key: 'outwear', name: 'Fashion' },
  { key: 'phones', name: 'Phones & tablets' }, { key: 'computing', name: 'Computing' },
  { key: 'sports', name: 'Sports & outdoors' }, { key: 'books', name: 'Books & more' },
];
