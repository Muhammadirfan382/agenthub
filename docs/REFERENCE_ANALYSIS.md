# Reference analysis: previous AgentHub prototype

This document records what was learned from the previous AgentHub prototype before
building the Phase 1 frontend. The prototype is a **UX and concept reference only**.
No code, markup or compiled HTML was copied into this project.

## Sources inspected

| Source | What was inspected |
| --- | --- |
| `agenthub-source/` (prototype source, v2.1.2) | Layout (`ConsoleLayout.tsx`), design tokens (`index.css`, `tailwind.config.ts`), primitives (`Primitives.tsx`: status, risk and verification badges, `MetricCard`, `PageHeader`, `EmptyState`, `ErrorState`), `AgentCard.tsx`, `DataTable.tsx`, `Dialog.tsx`, `ExecutionTimeline.tsx`, and the Dashboard, Marketplace, Agent detail, Executions, Security Center, Secrets, Permissions, Workflows and Settings pages |
| `agenthub-source/AUDIT.md` | Technical audit written on 2026-09-15 (known defects to avoid) |
| Portable build `AgentHub-2.1.2-Windows-no-install/AgentHub.html` | String-level inspection only. The in-app browser refused `file://` access, so no rendered screenshots were taken; visual conclusions come from source. |

## Findings by area

### Navigation structure and sidebar
- **Reference:** separate consoles (workspace, developer, admin) with a console switcher. The workspace sidebar grouped links into *Operate / Govern / Account*, used icon + label, supported collapse to icons, and turned into a sheet on mobile.
- **Kept:** grouped sidebar sections, icon + text labels, collapsible desktop sidebar, drawer on small screens, skip link.
- **Improved:** one console with seven top-level areas (Dashboard, Agents, Marketplace, Executions, Security, Analytics, Settings) instead of about 20 links across three consoles. The drawer uses the native modal `<dialog>` for a real focus trap. The reference drawer had no focus trap or focus restoration.

### Header
- **Reference:** logo, context breadcrumb, console switcher, search, notifications, theme toggle, avatar with a hard-coded demo user.
- **Kept:** theme toggle, account menu, primary "create" action.
- **Improved:** the header states *Demo mode*, and the account menu says *Demo session*. Sign-out is shown as not yet available rather than faked.

### Dashboard
- **Reference:** six metric cards, an installed-agents table, recent executions, a spend chart, security alerts and recommendations. Numbers came from mock data without saying so.
- **Kept:** metric card row, activity table, security emphasis.
- **Improved:** every data section is backed by the service layer with loading, error and empty states. A page-level notice and a *Demo data* badge on System status make clear these are simulated states.

### Agent cards and lists
- **Reference:** cards with category tint, name, publisher, tagline, badges and a footer row of rating, users, security score and price. The table view showed status, version, last run, cost and health.
- **Kept:** card anatomy (identity, description, badges, footer metadata) and a table/card view switch.
- **Improved:** status, verification and risk each use a badge with a text label, not only colour or icon. Row actions live in an accessible menu. Filters and sort are synced to the URL.

### Marketplace
- **Reference:** collection tabs, a large filter panel (15 filters), sort options, grid/list layout and invented usage/rating figures presented as real.
- **Kept:** collection tabs (All, Verified, Popular, Recently added), search, category filter, card grid.
- **Improved:** fewer, clearer filters (search, category, tag). Ratings, usage and security ratings are explicitly labelled demo figures ("demo ratings", "demo uses", "Security rating (demo)").

### Agent details
- **Reference:** a 12-tab profile (Overview, Capabilities, Tools, Permissions, Security, Privacy, Performance, Executions, Reviews, Versions, Developer, Support).
- **Kept:** tabbed detail page with header badges and primary actions.
- **Improved:** five focused tabs (Overview, Capabilities, Versions, Security, Executions), tab state in the URL, and an explicit note that permission indicators are configuration, not enforcement.

### Execution interface
- **Reference:** executions table with status tabs, and a detail page with an event timeline, error remediation and retries. Retry only showed a toast.
- **Kept:** timeline with a typed icon per event, error panel, tool usage.
- **Improved:** the eight defined states (QUEUED → TIMEOUT) each have a distinct label, icon and colour. The detail view adds tool call and log sections and states that the data is not real-time.

### Security interface
- **Reference:** posture metrics, events chart, risk distribution donut, events/policies/audit tabs and a kill switch that only set a `sessionStorage` flag while claiming to stop agents.
- **Kept:** risk distribution, events table, policy list.
- **Improved:** Low / Medium / High / Critical classifications with text labels, a permission overview table, an alerts list, and a prominent *Demo security data* notice. Nothing claims to enforce anything.

### Settings
- **Reference:** profile, organization, team, security, notifications, data tabs. Several controls reported success without doing anything (for example "Deleted 1,284 executions").
- **Kept:** tabbed settings.
- **Improved:** sections for Profile, Appearance, Notifications, Security, API and Agent preferences. Controls that cannot work yet are disabled or say "not saved". The API key field is a masked placeholder that never holds a real value. A real connection test calls the Phase 0 health endpoint.

## Visual language

| Aspect | Reference | Phase 1 decision |
| --- | --- | --- |
| Colour | Semantic HSL tokens, dark/light, indigo primary, risk scale low→critical | Semantic CSS variables exposed as Tailwind v4 utilities (`bg-surface`, `text-fg-muted`, `bg-danger-soft` …), indigo brand, same four-step risk scale, AA contrast targets |
| Typography | Inter with native fallbacks, 12–14 px body, 22–26 px page titles | System UI stack (no third-party font request), 14 px body, 24 px page titles, tabular numbers for metrics |
| Spacing and radius | 4 px grid, 7–12 px radii, subtle shadows | 4 px grid, 6–16 px radius scale, card and overlay shadow tokens |
| Icons | lucide-react via a name registry | lucide-react imported directly (tree-shaken), always paired with text |
| Status indicators | Coloured dot + label badges | Icon + label badges; colour is never the only signal |
| Tables | Real table on desktop, stacked cards on mobile (both rendered) | Same idea, but only one layout is rendered (media query), so content is not duplicated for screen readers |
| Forms | Field wrapper with label, hint and error | `Field` render prop wires `id`, `aria-describedby`, `aria-invalid` automatically; React Hook Form + Zod |
| Dialogs | Portal with manual focus trap | Native modal `<dialog>` (browser focus trap, inert background, Escape, focus return) |

## Problems deliberately not carried over
1. Mock data imported directly by components (bypassing services). The new project enforces the service layer with an ESLint rule.
2. Security controls simulated but presented as real (kill switch, revocation, "recorded in audit log").
3. Errors ignored in data hooks, so failures looked like empty lists. `QueryState` always distinguishes loading, error and empty states.
4. Hard-coded clock, user and organisation, and nav badge counts written as constants.
5. Clickable table rows that were not keyboard-operable. The new design uses links and menu buttons.
6. Very large multi-component page files. Pages are split into small feature components.
