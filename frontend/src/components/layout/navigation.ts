import type { LucideIcon } from 'lucide-react';
import { Activity, Bot, ChartColumn, LayoutDashboard, Settings, ShieldCheck, Store } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Workspace',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/agents', label: 'Agents', icon: Bot },
      { to: '/marketplace', label: 'Marketplace', icon: Store },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: '/executions', label: 'Executions', icon: Activity },
      { to: '/security', label: 'Security', icon: ShieldCheck },
      { to: '/analytics', label: 'Analytics', icon: ChartColumn },
    ],
  },
  {
    title: 'Account',
    items: [{ to: '/settings', label: 'Settings', icon: Settings }],
  },
];
