/**
 * The Content-Security-Policy for the built application.
 *
 * The production bundle loads nothing but its own scripts and stylesheet (and a
 * `data:` favicon), so the policy allows exactly that: no inline script, no
 * inline stylesheet, no eval, no plugins, no other origin - except the API,
 * when it is served from somewhere else (`VITE_API_BASE_URL`).
 *
 * It is applied as a `<meta>` tag at build time only. The development server
 * injects inline scripts for hot reload, which this policy would (correctly)
 * block. A meta tag cannot set `frame-ancestors`; the server that hosts the
 * build must send that one as a header (see docs/FRONTEND.md).
 *
 * Pure and dependency-free, so vite.config.ts and the tests can both use it.
 */
export function contentSecurityPolicy(apiBaseUrl: string | undefined): string {
  const connect = ["'self'"];
  const trimmed = apiBaseUrl?.trim();
  if (trimmed) {
    const origin = new URL(trimmed).origin;
    if (!/^https?:\/\//.test(origin)) throw new Error('VITE_API_BASE_URL must be an http(s) URL.');
    connect.push(origin);
  }
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src ${connect.join(' ')}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join('; ');
}
