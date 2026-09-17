import type {
  Execution,
  ExecutionDetail,
  ExecutionStatus,
  LogEntry,
  TimelineEvent,
  ToolCall,
} from '@/types/domain';
import { minutesAgo } from './time';

/*
 * DEMO DATA. Fictional executions. Nothing was actually run; timelines, logs
 * and tool calls are generated from templates and are not real-time.
 */

interface Seed {
  id: string;
  agentId: string;
  agentName: string;
  status: ExecutionStatus;
  startedMinutesAgo: number;
  durationMs: number | null;
  model: string;
  tokens: [number, number];
  tools: string[];
  result: string | null;
  trigger?: Execution['trigger'];
}

const seeds: Seed[] = [
  { id: 'exe_7f3a91c2', agentId: 'agt_threat_triage', agentName: 'Threat Triage', status: 'RUNNING', startedMinutesAgo: 3, durationMs: null, model: 'reasoning-large', tokens: [18420, 2210], tools: ['siem_query', 'siem_query'], result: null, trigger: 'api' },
  { id: 'exe_5b20d4e8', agentId: 'agt_research_scout', agentName: 'Research Scout', status: 'WAITING_FOR_TOOL', startedMinutesAgo: 14, durationMs: null, model: 'balanced-large', tokens: [9310, 1040], tools: ['web_search', 'document_reader'], result: null },
  { id: 'exe_c81e0f55', agentId: 'agt_incident_responder', agentName: 'Incident Responder', status: 'STARTING', startedMinutesAgo: 1, durationMs: null, model: 'reasoning-large', tokens: [0, 0], tools: [], result: null, trigger: 'api' },
  { id: 'exe_2d9b7a13', agentId: 'agt_support_drafter', agentName: 'Support Reply Drafter', status: 'QUEUED', startedMinutesAgo: 0, durationMs: null, model: 'fast-small', tokens: [0, 0], tools: [], result: null, trigger: 'schedule' },
  { id: 'exe_a4c6e210', agentId: 'agt_code_reviewer', agentName: 'Code Review Assistant', status: 'COMPLETED', startedMinutesAgo: 120, durationMs: 184_000, model: 'balanced-large', tokens: [42310, 5120], tools: ['repo_reader', 'test_runner', 'pr_comment'], result: '2 blocking issues and 3 suggestions posted to the pull request (demo).' },
  { id: 'exe_91fe3b07', agentId: 'agt_research_scout', agentName: 'Research Scout', status: 'COMPLETED', startedMinutesAgo: 190, durationMs: 97_000, model: 'balanced-large', tokens: [21870, 3380], tools: ['web_search', 'document_reader', 'citation_formatter'], result: 'Brief with 9 cited sources produced (demo).' },
  { id: 'exe_6e0d52aa', agentId: 'agt_incident_responder', agentName: 'Incident Responder', status: 'FAILED', startedMinutesAgo: 41, durationMs: 62_000, model: 'reasoning-large', tokens: [12040, 890], tools: ['cloud_inventory', 'runbook_executor'], result: null },
  { id: 'exe_3c7b18f9', agentId: 'agt_data_analyst', agentName: 'Data Insights Analyst', status: 'TIMEOUT', startedMinutesAgo: 2890, durationMs: 1_800_000, model: 'balanced-large', tokens: [88210, 4100], tools: ['sql_readonly', 'notebook_sandbox'], result: null },
  { id: 'exe_d05a6c34', agentId: 'agt_support_drafter', agentName: 'Support Reply Drafter', status: 'COMPLETED', startedMinutesAgo: 300, durationMs: 21_000, model: 'fast-small', tokens: [4020, 690], tools: ['kb_search', 'ticket_read', 'reply_draft'], result: 'Reply drafted and held for approval (demo).' },
  { id: 'exe_8a1f9e62', agentId: 'agt_threat_triage', agentName: 'Threat Triage', status: 'COMPLETED', startedMinutesAgo: 480, durationMs: 143_000, model: 'reasoning-large', tokens: [30550, 2980], tools: ['siem_query', 'ticket_create'], result: 'Alert classified as benign scanner traffic; ticket opened (demo).' },
  { id: 'exe_b7e4a019', agentId: 'agt_code_reviewer', agentName: 'Code Review Assistant', status: 'CANCELLED', startedMinutesAgo: 610, durationMs: 34_000, model: 'balanced-large', tokens: [6300, 120], tools: ['repo_reader'], result: null },
  { id: 'exe_4f2c8d71', agentId: 'agt_research_scout', agentName: 'Research Scout', status: 'COMPLETED', startedMinutesAgo: 1440, durationMs: 76_000, model: 'balanced-large', tokens: [17220, 2610], tools: ['web_search', 'document_reader'], result: 'Comparison table of 4 approaches produced (demo).' },
  { id: 'exe_e3d91b58', agentId: 'agt_invoice_reconciler', agentName: 'Invoice Reconciler', status: 'FAILED', startedMinutesAgo: 23040, durationMs: 12_000, model: 'balanced-large', tokens: [2100, 60], tools: ['erp_query'], result: null },
  { id: 'exe_1a6f47c3', agentId: 'agt_data_analyst', agentName: 'Data Insights Analyst', status: 'COMPLETED', startedMinutesAgo: 3100, durationMs: 412_000, model: 'balanced-large', tokens: [51400, 6120], tools: ['sql_readonly', 'chart_renderer'], result: 'Weekly anomaly report with 3 findings (demo).' },
];

const addMs = (iso: string, ms: number) => new Date(new Date(iso).getTime() + ms).toISOString();

function toExecution(seed: Seed): Execution {
  const startedAt = minutesAgo(seed.startedMinutesAgo);
  return {
    id: seed.id,
    agentId: seed.agentId,
    agentName: seed.agentName,
    status: seed.status,
    trigger: seed.trigger ?? 'manual',
    runtime: 'simulation',
    startedAt,
    endedAt: seed.durationMs === null ? null : addMs(startedAt, seed.durationMs),
    durationMs: seed.durationMs,
    model: seed.model,
    tokenUsage: { input: seed.tokens[0], output: seed.tokens[1] },
    toolCallCount: seed.tools.length,
    resultSummary: seed.result,
    requestedBy: 'Demo User',
    budget: { maxRuntimeSeconds: 900, maxTokens: 120000, maxToolCalls: 40 },
    cancelRequested: false,
    pendingApprovals: 0,
  };
}

export const demoExecutions: Execution[] = seeds.map(toExecution);

const TERMINAL_ERRORS: Partial<Record<ExecutionStatus, { code: string; message: string }>> = {
  FAILED: { code: 'tool_error', message: 'A tool call returned an error and the agent could not recover (demo).' },
  TIMEOUT: { code: 'runtime_limit_exceeded', message: 'The execution exceeded its maximum runtime of 1800 seconds (demo).' },
};

/** Builds a plausible, clearly synthetic detail view for a demo execution. */
export function buildDemoExecutionDetail(execution: Execution): ExecutionDetail {
  const seed = seeds.find((s) => s.id === execution.id);
  const tools = seed?.tools ?? [];
  const status = execution.status;
  const t0 = execution.startedAt;
  let offset = 0;
  const at = (stepMs: number) => addMs(t0, (offset += stepMs));

  const timeline: TimelineEvent[] = [{ id: 'tl_queued', at: t0, kind: 'lifecycle', label: 'Execution queued' }];
  const logs: LogEntry[] = [{ id: 'log_0', at: t0, level: 'info', message: `Execution ${execution.id} queued (trigger: ${execution.trigger}).` }];
  const toolCalls: ToolCall[] = [];

  if (status !== 'QUEUED') {
    const started = at(1200);
    timeline.push({ id: 'tl_sandbox', at: started, kind: 'lifecycle', label: 'Sandbox starting', detail: 'Isolated environment requested (simulated).' });
    logs.push({ id: 'log_1', at: started, level: 'debug', message: 'Resource limits applied from agent configuration.' });
  }

  if (!['QUEUED', 'STARTING'].includes(status)) {
    const modelAt = at(2400);
    timeline.push({ id: 'tl_model', at: modelAt, kind: 'model', label: `Model call: ${execution.model}`, detail: 'Operational metadata only; model reasoning is not recorded.' });
    logs.push({ id: 'log_2', at: modelAt, level: 'info', message: `Model ${execution.model} invoked.` });

    tools.forEach((tool, index) => {
      const isLast = index === tools.length - 1;
      const callAt = at(3000 + index * 1500);
      const toolStatus: ToolCall['status'] =
        isLast && status === 'FAILED' ? 'failed' : isLast && status === 'WAITING_FOR_TOOL' ? 'pending' : 'simulated';
      toolCalls.push({
        id: `tc_${index + 1}`,
        tool,
        capability: 'tool_calling',
        status: toolStatus,
        startedAt: callAt,
        durationMs: toolStatus === 'pending' ? null : 800 + index * 450,
        inputSummary: `Arguments validated against the ${tool} schema (demo).`,
        outputSummary:
          toolStatus === 'simulated'
            ? 'Simulated: no tool was invoked (demo).'
            : toolStatus === 'failed'
              ? 'Upstream service returned HTTP 503 (demo).'
              : null,
      });
      timeline.push({
        id: `tl_tool_${index + 1}`,
        at: callAt,
        kind: toolStatus === 'failed' ? 'error' : 'tool',
        label: toolStatus === 'pending' ? `Waiting for tool: ${tool}` : toolStatus === 'failed' ? `Tool failed: ${tool}` : `Tool call: ${tool}`,
      });
      logs.push({
        id: `log_tool_${index + 1}`,
        at: callAt,
        level: toolStatus === 'failed' ? 'error' : 'info',
        message:
          toolStatus === 'failed'
            ? `${tool} failed: upstream unavailable.`
            : `${tool} ${toolStatus === 'pending' ? 'in progress' : 'recorded as simulated'}.`,
      });
    });
  }

  const endAt = execution.endedAt ?? at(1000);
  if (status === 'COMPLETED') {
    timeline.push({ id: 'tl_result', at: endAt, kind: 'result', label: 'Execution completed', detail: execution.resultSummary ?? undefined });
    logs.push({ id: 'log_end', at: endAt, level: 'info', message: 'Execution completed successfully.' });
  } else if (status === 'FAILED' || status === 'TIMEOUT') {
    timeline.push({ id: 'tl_error', at: endAt, kind: 'error', label: status === 'FAILED' ? 'Execution failed' : 'Runtime limit reached' });
    logs.push({ id: 'log_end', at: endAt, level: 'error', message: TERMINAL_ERRORS[status]?.message ?? 'Execution ended with an error.' });
  } else if (status === 'CANCELLED') {
    timeline.push({ id: 'tl_cancel', at: endAt, kind: 'policy', label: 'Cancelled by user', detail: 'No partial results were written (demo).' });
    logs.push({ id: 'log_end', at: endAt, level: 'warn', message: 'Execution cancelled by a user.' });
  }

  return {
    ...execution,
    approvals: [],
    timeline,
    logs,
    toolCalls,
    error: TERMINAL_ERRORS[status] ?? null,
    result: status === 'COMPLETED' ? execution.resultSummary : null,
  };
}
