import { zodResolver } from '@hookform/resolvers/zod';
import { UserMinus } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useCurrentSession, usePermission } from '@/features/auth/api';
import { formatDateTime, formatRelative } from '@/lib/format';
import { hasRole } from '@/services/permissions';
import { toast } from '@/stores/toastStore';
import { type Member, ROLE_LABELS, ROLES, type Role } from '@/types/domain';
import { useAddMember, useMembers, useRemoveMember, useSetMemberRole } from '../api';

const addMemberSchema = z.object({
  email: z.email('Enter the email address of an existing account.').max(254),
  role: z.enum(['viewer', 'member', 'admin', 'owner']),
});

type AddMemberValues = z.infer<typeof addMemberSchema>;

function AddMemberCard({ actorRole }: { actorRole: Role }) {
  const add = useAddMember();
  const { register, handleSubmit, formState, reset } = useForm<AddMemberValues>({
    resolver: zodResolver(addMemberSchema),
    defaultValues: { email: '', role: 'member' },
  });

  // Nobody may grant a role above their own; the backend enforces this too.
  const assignable = ROLES.filter((role) => hasRole(actorRole, role));

  const onSubmit = handleSubmit((values) =>
    add.mutate(values, {
      onSuccess: (member) => {
        reset();
        toast.success(`${member.email} added`, `Role: ${ROLE_LABELS[member.role]}.`);
      },
      onError: (error) => toast.danger('Member could not be added', error.message),
    }),
  );

  return (
    <Card>
      <CardHeader
        title="Add a member"
        description="The account must already exist. AgentHub has no public sign-up: accounts are created with the create_user script."
      />
      <CardBody>
        <form noValidate onSubmit={onSubmit} aria-label="Add member" className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem]">
            <Field label="Email" required error={formState.errors.email?.message}>
              {(control) => (
                <Input {...control} {...register('email')} type="email" placeholder="person@example.com" />
              )}
            </Field>
            <Field label="Role" required error={formState.errors.role?.message}>
              {(control) => (
                <Select {...control} {...register('role')}>
                  {assignable.map((role) => (
                    <option key={role} value={role}>
                      {ROLE_LABELS[role]}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="flex justify-end">
            <Button type="submit" loading={add.isPending}>
              Add member
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function MemberTable({ members, actorRole, canManage }: { members: Member[]; actorRole: Role; canManage: boolean }) {
  const session = useCurrentSession();
  const setRole = useSetMemberRole();
  const remove = useRemoveMember();
  const [pendingRemoval, setPendingRemoval] = useState<Member | null>(null);

  const isSelf = (member: Member) => member.userId === session?.user.id;
  // An administrator may not touch an owner, and nobody edits their own row.
  const mayEdit = (member: Member) =>
    canManage && !isSelf(member) && (member.role !== 'owner' || actorRole === 'owner');

  const columns: Column<Member>[] = [
    {
      id: 'name',
      header: 'Member',
      primary: true,
      cell: (member) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-fg">
            {member.name}
            {isSelf(member) && <span className="ml-2 text-xs text-fg-subtle">(you)</span>}
          </p>
          <p className="truncate text-xs text-fg-muted">{member.email}</p>
        </div>
      ),
    },
    {
      id: 'role',
      header: 'Role',
      cell: (member) =>
        mayEdit(member) ? (
          <Select
            aria-label={`Role for ${member.name}`}
            value={member.role}
            disabled={setRole.isPending}
            onChange={(event) =>
              setRole.mutate(
                { id: member.id, role: event.target.value as Role },
                {
                  onSuccess: (updated) =>
                    toast.success(`${updated.name} is now ${ROLE_LABELS[updated.role].toLowerCase()}`),
                  onError: (error) => toast.danger('Role could not be changed', error.message),
                },
              )
            }
          >
            {ROLES.filter((role) => hasRole(actorRole, role)).map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </Select>
        ) : (
          <Badge tone={member.role === 'owner' ? 'brand' : 'neutral'}>{ROLE_LABELS[member.role]}</Badge>
        ),
    },
    {
      id: 'status',
      header: 'Status',
      hideOnMobile: true,
      cell: (member) => (
        <Badge tone={member.status === 'active' ? 'success' : 'warning'}>
          {member.status === 'active' ? 'Active' : 'Disabled'}
        </Badge>
      ),
    },
    {
      id: 'lastLogin',
      header: 'Last sign-in',
      hideOnMobile: true,
      cell: (member) => (
        <span className="whitespace-nowrap text-fg-muted">
          {member.lastLoginAt ? formatRelative(member.lastLoginAt) : 'Never'}
        </span>
      ),
    },
    {
      id: 'joined',
      header: 'Joined',
      hideOnMobile: true,
      cell: (member) => (
        <span className="whitespace-nowrap text-fg-muted">{formatDateTime(member.createdAt)}</span>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      cell: (member) =>
        mayEdit(member) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPendingRemoval(member)}
            aria-label={`Remove ${member.name}`}
          >
            <UserMinus aria-hidden="true" className="size-4" />
            Remove
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <DataTable columns={columns} rows={members} getRowKey={(member) => member.id} caption="Organization members" />
      <ConfirmDialog
        open={pendingRemoval !== null}
        tone="danger"
        title={pendingRemoval ? `Remove ${pendingRemoval.name}?` : 'Remove member?'}
        description="They lose access to this organization immediately, including any session they have open. Their account and agents are not deleted."
        confirmLabel="Remove member"
        pending={remove.isPending}
        onConfirm={() =>
          pendingRemoval &&
          remove.mutate(pendingRemoval.id, {
            onSuccess: () => {
              toast.success(`${pendingRemoval.name} removed`);
              setPendingRemoval(null);
            },
            onError: (error) => {
              toast.danger('Member could not be removed', error.message);
              setPendingRemoval(null);
            },
          })
        }
        onCancel={() => setPendingRemoval(null)}
      />
    </>
  );
}

export function MembersSettings() {
  const session = useCurrentSession();
  const permitted = usePermission();
  const query = useMembers();
  const canManage = permitted('member:manage');

  if (!session) return null;

  return (
    <div className="space-y-6">
      {!canManage && (
        <Alert tone="info" title="Read-only">
          Your role can see who belongs to {session.organization.name}, but only administrators and
          owners can add members or change roles.
        </Alert>
      )}

      <Card>
        <CardHeader
          title={`Members of ${session.organization.name}`}
          description="Roles decide what each person may do. The backend enforces them on every request."
        />
        <CardBody>
          <QueryState
            query={query}
            loading={<LoadingState variant="table" label="Loading members…" />}
            errorTitle="Members could not be loaded"
            empty={<EmptyState title="No members" description="Nobody belongs to this organization yet." />}
          >
            {(members) => <MemberTable members={members} actorRole={session.role} canManage={canManage} />}
          </QueryState>
        </CardBody>
      </Card>

      {canManage && <AddMemberCard actorRole={session.role} />}
    </div>
  );
}
