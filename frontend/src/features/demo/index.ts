/**
 * Centralised DEMO DATA for Phase 1.
 *
 * Everything exported here is fictional and exists only to exercise the UI.
 * Only `src/services/demo` may import it (enforced by ESLint); pages and
 * components receive data through the service layer.
 */
export { demoAgents } from './agents';
export { buildDemoExecutionDetail, demoExecutions } from './executions';
export { demoMarketplaceListings } from './marketplace';
export { demoPeople, demoUser } from './people';
export { demoComponentStatus, demoExecutionsPerDay, demoTokensPerDay } from './platform';
export { demoPolicies, demoSecurityEvents } from './security';
