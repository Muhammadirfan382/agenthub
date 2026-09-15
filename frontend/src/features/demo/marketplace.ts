import type { MarketplaceListing } from '@/types/domain';
import { daysAgo } from './time';

/*
 * DEMO DATA. Ratings, rating counts, usage counts and security ratings are
 * invented for UI demonstration. They are not real downloads, users, reviews,
 * execution statistics or security scan results.
 */
export const demoMarketplaceListings: MarketplaceListing[] = [
  { id: 'lst_research_scout', agentId: 'agt_research_scout', name: 'Research Scout', summary: 'Cited research briefs from approved sources.', category: 'research', tags: ['research', 'citations', 'summaries'], publisher: 'Maya Chen', verified: true, securityRating: 82, riskLevel: 'low', rating: 4.7, ratingCount: 128, demoUsageCount: 2400, publishedAt: daysAgo(120), popular: true },
  { id: 'lst_threat_triage', agentId: 'agt_threat_triage', name: 'Threat Triage', summary: 'Correlates alerts and drafts triage summaries.', category: 'security', tags: ['security', 'siem', 'triage'], publisher: 'Omar Haddad', verified: true, securityRating: 71, riskLevel: 'high', rating: 4.5, ratingCount: 86, demoUsageCount: 1150, publishedAt: daysAgo(210), popular: true },
  { id: 'lst_code_reviewer', agentId: 'agt_code_reviewer', name: 'Code Review Assistant', summary: 'Pull request review with sandboxed test runs.', category: 'engineering', tags: ['code-review', 'testing', 'github'], publisher: 'Lena Novak', verified: true, securityRating: 76, riskLevel: 'medium', rating: 4.6, ratingCount: 203, demoUsageCount: 3100, publishedAt: daysAgo(300), popular: true },
  { id: 'lst_data_analyst', agentId: 'agt_data_analyst', name: 'Data Insights Analyst', summary: 'Source-linked reports and anomaly detection.', category: 'data', tags: ['analytics', 'sql', 'reporting'], publisher: 'Priya Raman', verified: true, securityRating: 79, riskLevel: 'medium', rating: 4.4, ratingCount: 64, demoUsageCount: 870, publishedAt: daysAgo(160), popular: false },
  { id: 'lst_incident_responder', agentId: 'agt_incident_responder', name: 'Incident Responder', summary: 'Approval-gated infrastructure remediation.', category: 'operations', tags: ['incident', 'infrastructure', 'remediation'], publisher: 'Sam Okafor', verified: false, securityRating: 48, riskLevel: 'critical', rating: 4.1, ratingCount: 19, demoUsageCount: 140, publishedAt: daysAgo(10), popular: false },
  { id: 'lst_support_drafter', agentId: 'agt_support_drafter', name: 'Support Reply Drafter', summary: 'Knowledge-base replies held for human approval.', category: 'support', tags: ['support', 'drafting', 'knowledge-base'], publisher: 'Priya Raman', verified: true, securityRating: 86, riskLevel: 'low', rating: 4.8, ratingCount: 152, demoUsageCount: 1900, publishedAt: daysAgo(90), popular: true },
  { id: 'lst_seo_auditor', agentId: 'agt_seo_auditor', name: 'SEO Auditor', summary: 'Prioritised technical SEO fixes for sites you own.', category: 'marketing', tags: ['seo', 'crawler', 'audit'], publisher: 'Maya Chen', verified: false, securityRating: 74, riskLevel: 'low', rating: 3.9, ratingCount: 7, demoUsageCount: 35, publishedAt: daysAgo(4), popular: false },
];
