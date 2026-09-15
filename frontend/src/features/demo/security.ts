import type { PlatformPolicy, SecurityEvent } from '@/types/domain';
import { hoursAgo, minutesAgo, daysAgo } from './time';

/*
 * DEMO DATA. No security scanning or detection exists yet. These events and
 * policies illustrate how real findings will be presented from Phase 8 on.
 */
export const demoSecurityEvents: SecurityEvent[] = [
  { id: 'sev_1001', severity: 'critical', type: 'Permission escalation attempt', agentId: 'agt_incident_responder', agentName: 'Incident Responder', description: 'Requested write access to a production database outside its declared permissions.', detectedAt: minutesAgo(38), status: 'open' },
  { id: 'sev_1002', severity: 'high', type: 'Prompt injection pattern', agentId: 'agt_research_scout', agentName: 'Research Scout', description: 'Retrieved page contained instructions to exfiltrate data; content was treated as data.', detectedAt: hoursAgo(3), status: 'investigating' },
  { id: 'sev_1003', severity: 'high', type: 'Egress blocked', agentId: 'agt_threat_triage', agentName: 'Threat Triage', description: 'Attempted connection to a domain not on the allow-list.', detectedAt: hoursAgo(9), status: 'open' },
  { id: 'sev_1004', severity: 'medium', type: 'Approval timeout', agentId: 'agt_support_drafter', agentName: 'Support Reply Drafter', description: 'An outgoing reply waited more than 24 hours for approval and expired.', detectedAt: daysAgo(1), status: 'resolved' },
  { id: 'sev_1005', severity: 'medium', type: 'Resource limit reached', agentId: 'agt_data_analyst', agentName: 'Data Insights Analyst', description: 'Execution stopped at its runtime limit.', detectedAt: daysAgo(2), status: 'resolved' },
  { id: 'sev_1006', severity: 'low', type: 'Unused permission', agentId: 'agt_code_reviewer', agentName: 'Code Review Assistant', description: 'A granted permission has not been used in 30 days.', detectedAt: daysAgo(4), status: 'open' },
  { id: 'sev_1007', severity: 'critical', type: 'Verification rejected', agentId: 'agt_invoice_reconciler', agentName: 'Invoice Reconciler', description: 'Ledger write-back failed permission minimisation review; agent disabled.', detectedAt: daysAgo(15), status: 'resolved' },
];

export const demoPolicies: PlatformPolicy[] = [
  { id: 'pol_deny_default', name: 'Deny by default', description: 'Capabilities are unavailable unless explicitly granted to an agent.', enforcement: 'enforced' },
  { id: 'pol_approval_high', name: 'Approval for high-risk actions', description: 'High and critical risk actions pause until a person approves them.', enforcement: 'enforced' },
  { id: 'pol_untrusted_content', name: 'Retrieved content is untrusted', description: 'Instructions found in web pages, files or tool output are never executed.', enforcement: 'enforced' },
  { id: 'pol_egress', name: 'Egress allow-list', description: 'Agents may only reach domains listed in their security policy.', enforcement: 'monitoring' },
  { id: 'pol_secret_isolation', name: 'No secrets in sandboxes', description: 'Credentials are never placed inside agent execution environments.', enforcement: 'enforced' },
  { id: 'pol_unused_permissions', name: 'Unused permission review', description: 'Flag permissions not used within 30 days for removal.', enforcement: 'disabled' },
];
