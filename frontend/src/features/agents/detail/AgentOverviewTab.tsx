import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Card, CardHeader } from '@/components/ui/Card';
import { formatDateTime, formatNumber, formatRelative } from '@/lib/format';
import type { Agent } from '@/types/domain';

function DetailList({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-4 px-5 py-4 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs text-fg-subtle">{label}</dt>
          <dd className="mt-0.5 text-sm text-fg">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AgentOverviewTab({ agent }: { agent: Agent }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader title="Details" />
        <DetailList
          items={[
            ['Creator', agent.creator.name],
            ['Owner', agent.owner.name],
            ['Created', formatDateTime(agent.createdAt)],
            ['Last updated', formatDateTime(agent.updatedAt)],
            ['Last execution', agent.lastExecutionAt ? formatRelative(agent.lastExecutionAt) : 'Never'],
            ['Version', `v${agent.version}`],
          ]}
        />
        <div className="border-t border-line px-5 py-4">
          <p className="text-xs text-fg-subtle">Tags</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {agent.tags.map((tag) => (
              <li key={tag}>
                <Badge>{tag}</Badge>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card>
        <CardHeader title="Model configuration" description="Requested configuration. Models are not connected yet." />
        <DetailList
          items={[
            ['Provider', agent.model.provider],
            ['Model', agent.model.model],
            ['Temperature', agent.model.temperature],
            ['Max output tokens', formatNumber(agent.model.maxOutputTokens)],
          ]}
        />
      </Card>

      <Card>
        <CardHeader title="Tools" description="Tools declared in the agent configuration." />
        <ul className="flex flex-wrap gap-1.5 px-5 py-4">
          {agent.tools.length === 0 ? (
            <li className="text-sm text-fg-muted">No tools declared.</li>
          ) : (
            agent.tools.map((tool) => (
              <li key={tool}>
                <Badge tone="brand" className="font-mono">
                  {tool}
                </Badge>
              </li>
            ))
          )}
        </ul>
      </Card>

      <Card>
        <CardHeader title="Resource limits" />
        <DetailList
          items={[
            ['Max runtime', `${formatNumber(agent.resourceLimits.maxRuntimeSeconds)} s`],
            ['Max memory', `${formatNumber(agent.resourceLimits.maxMemoryMb)} MB`],
            ['Max tokens per run', formatNumber(agent.resourceLimits.maxTokensPerRun)],
            ['Max tool calls', formatNumber(agent.resourceLimits.maxToolCalls)],
          ]}
        />
      </Card>
    </div>
  );
}
