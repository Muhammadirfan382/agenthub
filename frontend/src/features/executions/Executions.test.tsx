import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { renderApp } from '@/test/renderApp';
import { EXECUTION_STATUSES } from '@/types/domain';

describe('execution status rendering', () => {
  it('renders a distinct text label for every execution state', () => {
    render(
      <ul>
        {EXECUTION_STATUSES.map((status) => (
          <li key={status}>
            <ExecutionStatusBadge status={status} />
          </li>
        ))}
      </ul>,
    );
    const labels = [
      'Queued',
      'Starting',
      'Running',
      'Waiting for tool',
      'Waiting for approval',
      'Completed',
      'Failed',
      'Cancelled',
      'Timed out',
    ];
    for (const label of labels) expect(screen.getByText(label)).toBeInTheDocument();
    expect(new Set(labels).size).toBe(EXECUTION_STATUSES.length);
  });

  it('lists executions and filters by status', async () => {
    const { user } = renderApp('/executions');
    const table = await screen.findByRole('table', { name: 'Agent executions' });
    expect(within(table).getAllByRole('row')).toHaveLength(15);

    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by status' }), 'TIMEOUT');
    expect(await screen.findByText('1 execution')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'exe_3c7b18f9' })).toBeInTheDocument();
  });
});

describe('execution details', () => {
  it('shows metadata, error, timeline, tool calls and logs for a failed execution', async () => {
    renderApp('/executions/exe_6e0d52aa');

    expect(await screen.findByRole('heading', { level: 1, name: 'exe_6e0d52aa' })).toBeInTheDocument();
    expect(screen.getByText('Demo data · not real-time')).toBeInTheDocument();
    expect(screen.getByText('Error: tool_error')).toBeInTheDocument();

    const timeline = screen.getByRole('list', { name: 'Execution timeline' });
    expect(within(timeline).getByText('Tool failed: runbook_executor')).toBeInTheDocument();

    const toolCalls = screen.getByRole('table', { name: 'Tool calls' });
    expect(within(toolCalls).getByText('Failed')).toBeInTheDocument();

    const logs = screen.getByRole('list', { name: 'Execution logs' });
    expect(within(logs).getAllByText('error').length).toBeGreaterThan(0);
  });

  it('shows a not-found state for an unknown execution', async () => {
    renderApp('/executions/exe_missing');
    expect(await screen.findByText('Execution not found')).toBeInTheDocument();
  });
});
