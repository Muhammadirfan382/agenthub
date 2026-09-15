import { Suspense, useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router';
import { LoadingState } from '@/components/feedback/LoadingState';
import { Toaster } from '@/components/feedback/Toaster';
import { useThemeEffect } from '@/hooks/useThemeEffect';
import { Header } from './Header';
import { MobileNav } from './MobileNav';
import { Sidebar } from './Sidebar';

export function AppShell() {
  useThemeEffect();
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  // Move focus to the main landmark after client-side navigation so screen
  // reader and keyboard users start at the new page content.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.scrollTo?.(0, 0);
    mainRef.current?.focus();
  }, [pathname]);

  return (
    <div className="flex min-h-dvh bg-canvas">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-brand px-3 py-2 text-sm font-medium text-brand-fg focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to main content
      </a>
      <Sidebar />
      <MobileNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main ref={mainRef} id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <Suspense fallback={<LoadingState label="Loading page…" />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
      <Toaster />
    </div>
  );
}
