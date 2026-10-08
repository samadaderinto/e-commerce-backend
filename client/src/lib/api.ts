export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

function message(data: unknown): string {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(message).join(' ');
  if (data && typeof data === 'object') {
    return Object.entries(data)
      .map(([key, value]) => {
        const prefix = key === 'detail' ? '' : `${key.replaceAll('_', ' ')}: `;
        return `${prefix}${message(value)}`;
      })
      .join(' ');
  }
  return 'Something went wrong. Please try again.';
}

export async function api<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  const multipart = data instanceof FormData;
  const headers = data && !multipart ? { 'Content-Type': 'application/json' } : undefined;
  const body = data ? (multipart ? data : JSON.stringify(data)) : undefined;

  const response = await fetch(`/api/${path}`, {
    method,
    signal: AbortSignal.timeout(25000),
    credentials: 'same-origin',
    headers,
    body,
  }).catch((error: unknown) => {
    if (error instanceof Error && (error.name === 'TimeoutError' || error.name === 'AbortError')) {
      throw new ApiError('The server took too long to respond. Please try again shortly.', 503);
    }
    throw error;
  });

  const result = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(message(result), response.status);
  }
  return result as T;
}

export const money = (value: string | number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(value));

export const categories = [
  { key: 'electronics', name: 'Electronics' },
  { key: 'outwear', name: 'Fashion' },
  { key: 'phones', name: 'Phones & tablets' },
  { key: 'computing', name: 'Computing' },
  { key: 'sports', name: 'Sports & outdoors' },
  { key: 'books', name: 'Books & more' },
];
