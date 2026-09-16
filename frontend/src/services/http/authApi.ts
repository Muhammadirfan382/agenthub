import { z } from 'zod';
import type {
  AuthService,
  Credentials,
  MemberService,
  PasswordChange,
  ProfileUpdate,
} from '@/services/contracts';
import type { ID, Member, Role, SessionInfo, UserProfile } from '@/types/domain';
import { apiRequest, apiRequestVoid } from './client';
import { orNull } from './orNull';
import { pageSchema } from './schemas';

/** Sessions and membership, served by `/api/v1/auth` and `/api/v1/members`. */

const role = z.enum(['viewer', 'member', 'admin', 'owner']);
const status = z.enum(['active', 'disabled']);

const UserSchema: z.ZodType<UserProfile> = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
  status,
  timezone: z.string(),
  createdAt: z.string(),
  lastLoginAt: z.string().nullable(),
});

const OrganizationSchema = z.object({ id: z.string(), name: z.string(), slug: z.string() });

const SessionSchema: z.ZodType<SessionInfo> = z.object({
  user: UserSchema,
  organization: OrganizationSchema,
  role,
  memberships: z.array(z.object({ organization: OrganizationSchema, role })),
  expiresAt: z.string(),
});

const MemberSchema: z.ZodType<Member> = z.object({
  id: z.string(),
  userId: z.string(),
  email: z.string(),
  name: z.string(),
  role,
  status,
  createdAt: z.string(),
  lastLoginAt: z.string().nullable(),
});

const MemberPageSchema = pageSchema(MemberSchema);

export const httpAuthService: AuthService = {
  /** A 401 here is the normal "signed out" answer, not a failure. */
  session(): Promise<SessionInfo | null> {
    return orNull(apiRequest('/api/v1/auth/session', SessionSchema), [401, 403]);
  },

  login(credentials: Credentials): Promise<SessionInfo> {
    return apiRequest('/api/v1/auth/login', SessionSchema, { method: 'POST', body: credentials });
  },

  logout(): Promise<void> {
    return apiRequestVoid('/api/v1/auth/logout', { method: 'POST' });
  },

  updateProfile(update: ProfileUpdate): Promise<UserProfile> {
    return apiRequest('/api/v1/auth/profile', UserSchema, { method: 'PATCH', body: update });
  },

  changePassword(change: PasswordChange): Promise<void> {
    return apiRequestVoid('/api/v1/auth/password', { method: 'POST', body: change });
  },

  switchOrganization(organizationId: ID): Promise<SessionInfo> {
    return apiRequest('/api/v1/auth/organization', SessionSchema, {
      method: 'POST',
      body: { organizationId },
    });
  },
};

export const httpMemberService: MemberService = {
  async list(): Promise<Member[]> {
    const page = await apiRequest('/api/v1/members?limit=200', MemberPageSchema);
    return page.items;
  },

  add(email: string, memberRole: Role): Promise<Member> {
    return apiRequest('/api/v1/members', MemberSchema, {
      method: 'POST',
      body: { email, role: memberRole },
    });
  },

  setRole(id: ID, memberRole: Role): Promise<Member> {
    return apiRequest(`/api/v1/members/${encodeURIComponent(id)}`, MemberSchema, {
      method: 'PATCH',
      body: { role: memberRole },
    });
  },

  remove(id: ID): Promise<void> {
    return apiRequestVoid(`/api/v1/members/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
};
