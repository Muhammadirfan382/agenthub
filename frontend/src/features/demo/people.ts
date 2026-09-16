import type { Member, Organization, Person, UserProfile } from '@/types/domain';

/** Fictional people for demonstration only. */
export const demoPeople = {
  maya: { id: 'usr_demo_maya', name: 'Maya Chen' },
  omar: { id: 'usr_demo_omar', name: 'Omar Haddad' },
  lena: { id: 'usr_demo_lena', name: 'Lena Novak' },
  sam: { id: 'usr_demo_sam', name: 'Sam Okafor' },
  priya: { id: 'usr_demo_priya', name: 'Priya Raman' },
} satisfies Record<string, Person>;

/** The signed-in profile in demo mode. Nothing here was authenticated. */
export const demoUser: UserProfile = {
  id: 'usr_demo_current',
  name: 'Demo User',
  email: 'demo.user@example.com',
  status: 'active',
  timezone: 'UTC',
  createdAt: '2026-01-05T09:00:00.000Z',
  lastLoginAt: '2026-09-16T08:00:00.000Z',
};

export const demoOrganization: Organization = {
  id: 'org_demo_workspace',
  name: 'Demo Workspace',
  slug: 'demo-workspace',
};

/** Fictional members, so the members screen has something to show. */
export const demoMembers: Member[] = [
  {
    id: 'mem_demo_current',
    userId: demoUser.id,
    email: demoUser.email,
    name: demoUser.name,
    role: 'owner',
    status: 'active',
    createdAt: '2026-01-05T09:00:00.000Z',
    lastLoginAt: '2026-09-16T08:00:00.000Z',
  },
  {
    id: 'mem_demo_maya',
    userId: demoPeople.maya.id,
    email: 'maya.chen@example.com',
    name: demoPeople.maya.name,
    role: 'admin',
    status: 'active',
    createdAt: '2026-02-11T10:30:00.000Z',
    lastLoginAt: '2026-09-15T16:20:00.000Z',
  },
  {
    id: 'mem_demo_omar',
    userId: demoPeople.omar.id,
    email: 'omar.haddad@example.com',
    name: demoPeople.omar.name,
    role: 'member',
    status: 'active',
    createdAt: '2026-03-02T08:15:00.000Z',
    lastLoginAt: '2026-09-12T11:05:00.000Z',
  },
  {
    id: 'mem_demo_lena',
    userId: demoPeople.lena.id,
    email: 'lena.novak@example.com',
    name: demoPeople.lena.name,
    role: 'viewer',
    status: 'active',
    createdAt: '2026-04-19T13:45:00.000Z',
    lastLoginAt: null,
  },
];
