import type { AgentPermission, RiskLevel } from '@/types/domain';

export const RISK_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

const BASE_SCORE: Record<RiskLevel, number> = { low: 15, medium: 40, high: 65, critical: 85 };

/**
 * Indicative risk derived from the permissions an agent requests.
 *
 * This is a UX estimate for the frontend. It is NOT a security control and
 * will be replaced by a server-side assessment.
 */
export function deriveRisk(permissions: AgentPermission[]): { level: RiskLevel; score: number } {
  const granted = permissions.filter((p) => p.level !== 'denied');
  if (granted.length === 0) return { level: 'low', score: 5 };

  const level = granted.reduce<RiskLevel>(
    (highest, p) => (RISK_RANK[p.risk] > RISK_RANK[highest] ? p.risk : highest),
    'low',
  );
  const breadth = Math.min(10, granted.length * 2);
  const unguardedHighRisk = granted.filter((p) => RISK_RANK[p.risk] >= RISK_RANK.high && !p.requiresApproval).length;
  const score = Math.min(100, BASE_SCORE[level] + breadth + unguardedHighRisk * 3);
  return { level, score };
}
