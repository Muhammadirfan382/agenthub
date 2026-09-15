import { useEffect } from 'react';
import { applyTheme, useUiStore } from '@/stores/uiStore';

/** Keeps the <html> theme class in sync with the preference and the OS setting. */
export function useThemeEffect(): void {
  const theme = useUiStore((state) => state.theme);

  useEffect(() => {
    applyTheme(theme);
    if (theme !== 'system' || typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => applyTheme('system');
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [theme]);
}
