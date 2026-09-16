import { describe, expect, it } from 'vitest';
import { can, hasRole } from './permissions';

/**
 * These expectations must match backend/app/services/authorization.py. If the
 * two ever disagree, the backend wins: it is the one that enforces.
 */
describe('permission matrix', () => {
  it('orders the roles', () => {
    expect(hasRole('owner', 'admin')).toBe(true);
    expect(hasRole('admin', 'member')).toBe(true);
    expect(hasRole('member', 'admin')).toBe(false);
    expect(hasRole('viewer', 'member')).toBe(false);
  });

  it('lets a viewer read and nothing else', () => {
    expect(can('viewer', 'agent:read')).toBe(true);
    expect(can('viewer', 'execution:read')).toBe(true);
    expect(can('viewer', 'member:read')).toBe(true);
    expect(can('viewer', 'agent:create')).toBe(false);
    expect(can('viewer', 'agent:update')).toBe(false);
    expect(can('viewer', 'agent:update', { ownsResource: true })).toBe(false);
  });

  it('lets a member manage only their own agents', () => {
    expect(can('member', 'agent:create')).toBe(true);
    expect(can('member', 'agent:update', { ownsResource: true })).toBe(true);
    expect(can('member', 'agent:delete', { ownsResource: true })).toBe(true);
    expect(can('member', 'agent:execute', { ownsResource: true })).toBe(true);
    expect(can('member', 'agent:update')).toBe(false);
    expect(can('member', 'member:manage', { ownsResource: true })).toBe(false);
  });

  it('lets an administrator manage anything except the organization itself', () => {
    expect(can('admin', 'agent:update')).toBe(true);
    expect(can('admin', 'agent:delete')).toBe(true);
    expect(can('admin', 'member:manage')).toBe(true);
    expect(can('admin', 'organization:manage')).toBe(false);
    expect(can('owner', 'organization:manage')).toBe(true);
  });

  it('refuses everything when there is no session', () => {
    expect(can(undefined, 'agent:read')).toBe(false);
    expect(can(undefined, 'agent:create', { ownsResource: true })).toBe(false);
  });
});
