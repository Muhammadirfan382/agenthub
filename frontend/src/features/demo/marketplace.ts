import type { Installation, MarketplaceListing, PermissionGrant } from '@/types/domain';
import { daysAgo } from './time';

/*
 * DEMO DATA. Ratings, rating counts, usage counts and security ratings are
 * invented for UI demonstration and live in `demoStats`, which the real API
 * never returns. They are not real downloads, users, reviews, execution
 * statistics or security scan results.
 */

function listing(
  partial: Omit<MarketplaceListing, 'installed' | 'installationId' | 'own' | 'visibility'> &
    Partial<Pick<MarketplaceListing, 'installed' | 'installationId' | 'own' | 'visibility'>>,
): MarketplaceListing {
  return {
    visibility: 'public',
    installed: false,
    installationId: null,
    own: false,
    ...partial,
  };
}

export const demoMarketplaceListings: MarketplaceListing[] = [
  listing({
    id: 'ver_demo_research_scout',
    agentId: 'agt_research_scout',
    name: 'Research Scout',
    summary: 'Cited research briefs from approved sources.',
    category: 'research',
    tags: ['research', 'citations', 'summaries'],
    version: '2.3.1',
    publisher: 'Northwind Labs',
    verification: 'verified',
    riskLevel: 'low',
    riskScore: 22,
    tools: ['web_search', 'document_reader'],
    publishedAt: daysAgo(120),
    own: true,
    demoStats: { rating: 4.7, ratingCount: 128, usageCount: 2400, securityRating: 82 },
  }),
  listing({
    id: 'ver_demo_threat_triage',
    agentId: 'agt_threat_triage',
    name: 'Threat Triage',
    summary: 'Correlates alerts and drafts triage summaries.',
    category: 'security',
    tags: ['security', 'siem', 'triage'],
    version: '1.8.0',
    publisher: 'Northwind Labs',
    verification: 'verified',
    riskLevel: 'high',
    riskScore: 68,
    tools: ['api_request', 'chart_renderer'],
    publishedAt: daysAgo(210),
    own: true,
    visibility: 'organization',
    demoStats: { rating: 4.5, ratingCount: 86, usageCount: 1150, securityRating: 71 },
  }),
  listing({
    id: 'ver_demo_code_reviewer',
    agentId: 'agt_code_reviewer',
    name: 'Code Review Assistant',
    summary: 'Pull request review with sandboxed test runs.',
    category: 'engineering',
    tags: ['code-review', 'testing', 'github'],
    version: '3.0.2',
    publisher: 'Beacon Tools',
    verification: 'verified',
    riskLevel: 'critical',
    riskScore: 84,
    tools: ['code_sandbox', 'document_reader'],
    publishedAt: daysAgo(300),
    demoStats: { rating: 4.6, ratingCount: 203, usageCount: 3100, securityRating: 76 },
  }),
  listing({
    id: 'ver_demo_data_analyst',
    agentId: 'agt_data_analyst',
    name: 'Data Insights Analyst',
    summary: 'Source-linked reports and anomaly detection.',
    category: 'data',
    tags: ['analytics', 'sql', 'reporting'],
    version: '1.4.0',
    publisher: 'Beacon Tools',
    verification: 'verified',
    riskLevel: 'medium',
    riskScore: 44,
    tools: ['sql_readonly', 'chart_renderer'],
    publishedAt: daysAgo(160),
    demoStats: { rating: 4.4, ratingCount: 64, usageCount: 870, securityRating: 79 },
  }),
  listing({
    id: 'ver_demo_incident_responder',
    agentId: 'agt_incident_responder',
    name: 'Incident Responder',
    summary: 'Approval-gated infrastructure remediation.',
    category: 'operations',
    tags: ['incident', 'infrastructure', 'remediation'],
    version: '0.9.0',
    publisher: 'Helio Systems',
    verification: 'unverified',
    riskLevel: 'critical',
    riskScore: 91,
    tools: ['api_request', 'code_sandbox'],
    publishedAt: daysAgo(10),
    demoStats: { rating: 4.1, ratingCount: 19, usageCount: 140, securityRating: 48 },
  }),
  listing({
    id: 'ver_demo_support_drafter',
    agentId: 'agt_support_drafter',
    name: 'Support Reply Drafter',
    summary: 'Knowledge-base replies held for human approval.',
    category: 'support',
    tags: ['support', 'drafting', 'knowledge-base'],
    version: '2.1.0',
    publisher: 'Helio Systems',
    verification: 'verified',
    riskLevel: 'medium',
    riskScore: 39,
    tools: ['document_reader', 'email_draft'],
    publishedAt: daysAgo(90),
    installed: true,
    installationId: 'ins_demo_support_drafter',
    demoStats: { rating: 4.8, ratingCount: 152, usageCount: 1900, securityRating: 86 },
  }),
  listing({
    id: 'ver_demo_seo_auditor',
    agentId: 'agt_seo_auditor',
    name: 'SEO Auditor',
    summary: 'Prioritised technical SEO fixes for sites you own.',
    category: 'marketing',
    tags: ['seo', 'crawler', 'audit'],
    version: '0.3.0',
    publisher: 'Helio Systems',
    verification: 'unverified',
    riskLevel: 'low',
    riskScore: 18,
    tools: ['web_search'],
    publishedAt: daysAgo(4),
    demoStats: { rating: 3.9, ratingCount: 7, usageCount: 35, securityRating: 74 },
  }),
];

function grant(
  capability: PermissionGrant['capability'],
  level: PermissionGrant['level'],
  scope: string,
  risk: PermissionGrant['risk'] = 'low',
  requiresApproval = false,
): PermissionGrant {
  return { capability, level, requiresApproval, scope, risk };
}

/** One installed agent, granted less than its manifest asks for. */
export const demoInstallations: Installation[] = [
  {
    id: 'ins_demo_support_drafter',
    agentId: 'agt_support_drafter',
    agentVersionId: 'ver_demo_support_drafter',
    agentName: 'Support Reply Drafter',
    publisher: 'Helio Systems',
    version: '2.1.0',
    status: 'active',
    grants: [
      grant('web_access', 'denied', 'Not granted'),
      grant('api_access', 'denied', 'Not granted'),
      grant('file_access', 'read_only', 'Support knowledge base'),
      grant('database_access', 'denied', 'Not granted'),
      grant('tool_calling', 'restricted', 'Declared drafting tools', 'medium'),
      grant('code_execution', 'denied', 'Not granted'),
      grant('email_send', 'denied', 'Not granted'),
    ],
    riskLevel: 'medium',
    riskScore: 34,
    note: 'Drafts only. Sending email was not granted.',
    installedBy: 'Demo User',
    createdAt: daysAgo(21),
    updatedAt: daysAgo(3),
    unusableTools: ['email_draft'],
    updateAvailable: false,
  },
];
