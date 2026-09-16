/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public backend base URL. Empty means same-origin. Never a secret. */
  readonly VITE_API_BASE_URL?: string;
  /** Which services the app starts with: 'demo' (default) or 'api'. */
  readonly VITE_DATA_SOURCE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
