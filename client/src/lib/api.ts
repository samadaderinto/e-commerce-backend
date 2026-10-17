export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

const pendingApiRequests = new Set<AbortController>();

/** Abort browser requests that could still refresh and restore an auth cookie. */
export function cancelPendingApiRequests(): void {
  for (const controller of pendingApiRequests) {
    controller.abort();
  }
  pendingApiRequests.clear();
}

function cleanErrorMessage(str: string): string {
  const errorDetailMatch = /ErrorDetail\(string=['"](.*?)['"],\s*code=['"].*?['"]\)/.exec(str);
  if (errorDetailMatch) {
    return errorDetailMatch[1];
  }
  const pyDictMatch = /\{['"][^'"]+['"]:\s*['"](.*?)['"]\}/.exec(str);
  if (pyDictMatch) {
    return pyDictMatch[1];
  }
  return str;
}

function message(data: unknown): string {
  if (typeof data === 'string') return cleanErrorMessage(data);
  if (Array.isArray(data)) return data.map(message).join(' ');
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (obj.error && typeof obj.error === 'object') {
      const errObj = obj.error as Record<string, unknown>;
      const errMessage = typeof errObj.message === 'string' ? cleanErrorMessage(errObj.message) : '';
      if (errMessage && errMessage !== 'Request validation failed.') {
        return errMessage;
      }
      if (errObj.details) {
        return message(errObj.details);
      }
      if (errMessage) {
        return errMessage;
      }
    }
    return Object.entries(data)
      .map(([key, value]) => {
        const cleanVal = message(value);
        const prefix = (
          key === 'detail' ||
          key === 'error' ||
          key === 'errors' ||
          key === 'message' ||
          key === 'code' ||
          key === 'coupon' ||
          key === 'non_field_errors'
        )
          ? ''
          : `${key.replaceAll('_', ' ')}: `;
        return `${prefix}${cleanVal}`;
      })
      .join(' ');
  }
  return 'Something went wrong. Please try again.';
}

export async function api<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  const multipart = data instanceof FormData;
  const headers = data && !multipart ? { 'Content-Type': 'application/json' } : undefined;
  const body = data ? (multipart ? data : JSON.stringify(data)) : undefined;
  const controller = new AbortController();
  pendingApiRequests.add(controller);

  try {
    const response = await fetch(`/api/${path}`, {
      method,
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(25000)]),
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
  } finally {
    pendingApiRequests.delete(controller);
  }
}

export const money = (value: string | number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(value));

export const categories: { key: string; name: string }[] = [
  { key: 'electronics', name: 'Electronics' },
  { key: 'outwear', name: 'Fashion' },
  { key: 'phones', name: 'Phones' },
  { key: 'computing', name: 'Computing' },
  { key: 'sports', name: 'Sports & outdoors' },
  { key: 'books', name: 'Books' },
  { key: 'toys', name: 'Toys & games' },
  { key: 'kids', name: 'Kids & baby' },
  { key: 'home', name: 'Home & living' },
  { key: 'kitchen', name: 'Kitchen & dining' },
  { key: 'beauty', name: 'Beauty & personal care' },
  { key: 'health', name: 'Health & wellness' },
  { key: 'pets', name: 'Pet supplies' },
  { key: 'games', name: 'Gaming' },
  { key: 'tablets', name: 'Tablets' },
  { key: 'fishing', name: 'Fishing' },
  { key: 'lingerie', name: 'Lingerie & sleepwear' },
  { key: 'beverages', name: 'Coffee, tea & drinks' },
  { key: 'garden', name: 'Garden & tools' },
  { key: 'automotive', name: 'Automotive' },
  { key: 'jewelry', name: 'Jewelry & watches' },
  { key: 'software', name: 'Software & apps' },
  { key: 'courses', name: 'Courses & learning' },
  { key: 'templates', name: 'Templates & planners' },
  { key: 'design_assets', name: 'Design assets' },
  { key: 'photo_video', name: 'Photos & video' },
  { key: 'music_audio', name: 'Music & audio' },
  { key: 'business', name: 'Business resources' },
  { key: 'digital_tools', name: 'Digital tools & presets' },
];
