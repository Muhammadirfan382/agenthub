import type { Person, UserProfile } from '@/types/domain';

/** Fictional people for demonstration only. */
export const demoPeople = {
  maya: { id: 'usr_demo_maya', name: 'Maya Chen' },
  omar: { id: 'usr_demo_omar', name: 'Omar Haddad' },
  lena: { id: 'usr_demo_lena', name: 'Lena Novak' },
  sam: { id: 'usr_demo_sam', name: 'Sam Okafor' },
  priya: { id: 'usr_demo_priya', name: 'Priya Raman' },
} satisfies Record<string, Person>;

/** Placeholder profile shown while authentication does not exist (Phase 3). */
export const demoUser: UserProfile = {
  id: 'usr_demo_current',
  name: 'Demo User',
  email: 'demo.user@example.com',
  role: 'Workspace admin (demo)',
  timezone: 'UTC',
};
