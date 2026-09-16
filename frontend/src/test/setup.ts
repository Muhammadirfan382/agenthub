import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Route modules are lazy-loaded; the first import in jsdom can be slow, and
// slower still when every test file runs in its own worker.
configure({ asyncUtilTimeout: 10000 });
import { useDataSourceStore } from '@/stores/dataSourceStore';
import { useToastStore } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

// jsdom implements HTMLDialogElement without showModal()/close().
if (typeof HTMLDialogElement !== 'undefined') {
  if (typeof HTMLDialogElement.prototype.showModal !== 'function') {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
  }
  if (typeof HTMLDialogElement.prototype.close !== 'function') {
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      if (!this.hasAttribute('open')) return;
      this.removeAttribute('open');
      this.dispatchEvent(new Event('close'));
    };
  }
}

// jsdom logs "not implemented" for scrollTo; the shell scrolls on navigation.
window.scrollTo = () => undefined;

// jsdom has no matchMedia. Report a desktop-width viewport so tests exercise
// the table layout; responsive card layouts are covered where relevant.
if (typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: /min-width/.test(query),
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  useToastStore.setState({ toasts: [] });
  useUiStore.setState({ theme: 'system', sidebarCollapsed: false, mobileNavOpen: false });
  useDataSourceStore.setState({ dataSource: 'demo' });
  localStorage.clear();
});
