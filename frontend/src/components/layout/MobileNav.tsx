import { X } from 'lucide-react';
import type { MouseEvent, SyntheticEvent } from 'react';
import { useEffect, useRef } from 'react';
import { useUiStore } from '@/stores/uiStore';
import { Logo } from './Logo';
import { SidebarNav } from './SidebarNav';

/** Navigation drawer for small screens, built on the native modal <dialog>. */
export function MobileNav() {
  const open = useUiStore((state) => state.mobileNavOpen);
  const setOpen = useUiStore((state) => state.setMobileNavOpen);
  if (!open) return null;
  return <Drawer onClose={() => setOpen(false)} />;
}

function Drawer({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const onCancel = (event: SyntheticEvent) => {
    event.preventDefault();
    onClose();
  };

  const onBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) onClose();
  };

  return (
    <dialog
      ref={ref}
      aria-label="Navigation"
      onCancel={onCancel}
      onClick={onBackdrop}
      className="m-0 h-dvh max-h-dvh w-72 max-w-[85vw] border-r border-line bg-surface p-0 text-fg shadow-overlay lg:hidden"
    >
      <div className="flex h-14 items-center justify-between border-b border-line px-4">
        <Logo />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close navigation"
          className="rounded-md p-1.5 text-fg-subtle hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      </div>
      <div className="px-3 py-4">
        <SidebarNav onNavigate={onClose} />
      </div>
    </dialog>
  );
}
