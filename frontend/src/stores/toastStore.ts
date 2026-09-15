import { create } from 'zustand';

export type ToastTone = 'success' | 'info' | 'warning' | 'danger';

export interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, 'id'>) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;
const MAX_VISIBLE = 4;

/** Shared feedback queue: any page can raise a toast; the shell renders them. */
export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],
  push: (toast) =>
    set((state) => ({ toasts: [...state.toasts, { ...toast, id: nextId++ }].slice(-MAX_VISIBLE) })),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  success: (title: string, description?: string) => useToastStore.getState().push({ title, description, tone: 'success' }),
  info: (title: string, description?: string) => useToastStore.getState().push({ title, description, tone: 'info' }),
  warning: (title: string, description?: string) => useToastStore.getState().push({ title, description, tone: 'warning' }),
  danger: (title: string, description?: string) => useToastStore.getState().push({ title, description, tone: 'danger' }),
};
