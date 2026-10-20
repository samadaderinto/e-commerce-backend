import type { APIRequestContext, APIResponse, Response } from '@playwright/test';

/** Respect the real gateway limits without bypassing production controls. */
export async function waitForAuthRetry(response: APIResponse | Response): Promise<void> {
  const headers: Record<string, string> = await response.headers();
  const retryAfter: number = Number(headers['retry-after'] || 60);
  const seconds: number = Number.isFinite(retryAfter)
    ? Math.min(60, Math.max(1, retryAfter))
    : 60;
  await new Promise<void>(resolve => setTimeout(resolve, seconds * 1000));
}

export async function postAuthWithRetry(
  request: APIRequestContext,
  path: string,
  options: Parameters<APIRequestContext['post']>[1],
): Promise<APIResponse> {
  let response: APIResponse = await request.post(path, options);
  for (let attempt: number = 0; response.status() === 429 && attempt < 2; attempt += 1) {
    await waitForAuthRetry(response);
    response = await request.post(path, options);
  }
  return response;
}
