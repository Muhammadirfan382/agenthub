import { ApiError } from './client';

/**
 * A missing resource is a normal answer for detail views, not a failure.
 * Session reads pass 401/403 too: "nobody is signed in" is an answer, not an error.
 */
export async function orNull<T>(request: Promise<T>, statuses: number[] = [404]): Promise<T | null> {
  try {
    return await request;
  } catch (error) {
    if (error instanceof ApiError && statuses.includes(error.status)) return null;
    throw error;
  }
}
