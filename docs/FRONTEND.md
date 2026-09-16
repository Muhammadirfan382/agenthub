# AgentHub frontend

> **Status (Phase 1):** the frontend runs entirely on demonstration data.
>
> - **Backend integration is not yet implemented.**
> - **Authentication is not yet implemented.**
> - **Real agent execution is not yet implemented.**
> - **Real security scanning is not yet implemented.**
>
> The one exception is **Settings → API → Test connection**, which calls the real
> Phase 0 endpoint `GET /api/v1/health`.

## 1. Architecture

```
frontend/src/
├── main.tsx                 Entry: applies saved theme, renders <App/>
├── app/                     App wiring: App, AppProviders, routes, queryClient
├── config/env.ts            Validated public configuration (VITE_API_BASE_URL)
├── types/domain.ts          API models: the UI ↔ service contract
├── services/
│   ├── contracts.ts         Service interfaces (AgentService, ExecutionService, …)
│   ├── index.ts             createServices(): chooses the implementation
│   ├── ServicesContext.ts   useServices() hook
│   ├── ServicesProvider.tsx Context provider
│   ├── queryKeys.ts         Central TanStack Query keys
│   ├── http/                The only place that calls fetch()
│   │   ├── client.ts        apiRequest(): base URL, timeout, typed errors, Zod validation
│   │   └── systemApi.ts     Real GET /api/v1/health
│   └── demo/                Demo implementations of every contract (in-memory)
├── features/                One folder per product area
│   ├── demo/                Centralised DEMO DATA (import-restricted)
│   ├── dashboard/  agents/  marketplace/  executions/
│   ├── security/   analytics/  settings/  errors/
│   └── <area>/api.ts        TanStack Query hooks for that area
├── components/
│   ├── ui/                  Design-system primitives
│   ├── feedback/            LoadingState, EmptyState, ErrorState, QueryState, Toaster, DemoNotice
│   ├── status/              Status, risk, verification, permission indicators + label metadata
│   ├── layout/              AppShell, Sidebar, MobileNav, Header, PageHeader, ThemeToggle, UserMenu
│   └── charts/              Dependency-free BarChart with accessible data table
├── stores/                  Zustand: uiStore (theme, sidebar), toastStore
├── hooks/                   useMediaQuery, useDocumentTitle, useThemeEffect
├── lib/                     cn, format (dates/durations/numbers), risk (indicative UX estimate)
├── styles/index.css         Tailwind v4 + design tokens (light/dark)
└── test/                    Vitest setup and renderApp() harness
```

Data flows in one direction only:

```
Page / component → feature hook (TanStack Query) → useServices() → service contract → demo or HTTP implementation
```

Components never import demo data and never call `fetch`. ESLint enforces the
first rule (`no-restricted-imports` on `@/features/demo`).

## 2. Routing

React Router (data router) with lazy-loaded pages. The route table is in
`src/app/routes.tsx`.

| Path | Page |
| --- | --- |
| `/` | Redirects to `/dashboard` |
| `/dashboard` | Dashboard |
| `/agents` | Agent list |
| `/agents/create` | Create agent |
| `/agents/:id` | Agent details (`?tab=capabilities\|versions\|security\|executions`) |
| `/agents/:id/edit` | Edit agent |
| `/marketplace` | Marketplace (`?collection=`, `?q=`, `?category=`, `?tag=`) |
| `/executions` | Executions (`?status=`, `?q=`) |
| `/executions/:id` | Execution details |
| `/security` | Security dashboard |
| `/analytics` | Analytics |
| `/settings` | Settings (`?section=profile\|appearance\|notifications\|security\|api\|agents`) |
| `*` | 404 page (inside the shell) |

- **Route loading:** `AppShell` wraps the `<Outlet/>` in `Suspense` with a `LoadingState`.
- **Route errors:** two `errorElement` boundaries. One is page-level and keeps the shell visible; the other is a last resort if the shell itself fails. Error details and stack traces are never rendered.
- **Focus management:** after client-side navigation, focus moves to `<main>` for keyboard and screen-reader users.

## 3. Component architecture

- **Primitives (`components/ui`):**
  - Actions and inputs: `Button`/`LinkButton`, `Input`, `Textarea`, `Select` (native), `Checkbox`, `Switch` (`role="switch"`), `SearchInput`.
  - Form wiring: `Field`, a render prop that wires the label, hint, error and ARIA attributes to its control.
  - Display: `Badge`, `Card`/`CardHeader`/`CardBody`, `Alert`, `Skeleton`, `Spinner`, `Meter` (progressbar), `StatCard`.
  - Interactive: `Tabs`/`TabPanel` (roving tabindex), `Tooltip` (hover/focus, Escape), `Dialog` (native modal `<dialog>`), `ConfirmDialog`, `DropdownMenu` (menu button pattern), `DataTable`.
  - Class composition: shared style functions in `buttonStyles.ts` and `controlStyles.ts` avoid duplicated class lists.
- **`DataTable`** renders a semantic `<table>` from 768 px up and stacked cards below. Only one layout is mounted, so content isn't duplicated for assistive technology. It supports sortable headers with `aria-sort`.
- **Feedback:** `QueryState` renders a query's loading, error (with retry) and empty states consistently. A failed request is never shown as an empty list.
- **Status (`components/status`):** every badge has a text label, and icon and colour are supplementary. `meta.ts` centralises labels, tones and icons for execution states, risk, agent status, verification, permission levels, component states, security checks, events and policies.
- **Features** are split into small components (for example `features/agents/detail/*Tab.tsx` and `features/agents/form/sections/*.tsx`).

### Design system

Tokens live in `src/styles/index.css` as CSS variables and are exposed as Tailwind v4
utilities through `@theme inline`:

- **Surfaces:** `canvas`, `surface`, `surface-muted`, `surface-hover`, `line`, `line-strong`.
- **Text:** `fg`, `fg-muted`, `fg-subtle`.
- **Brand:** `brand`, `brand-hover`, `brand-fg`, `brand-soft`, `brand-strong`.
- **Status:** `success`, `warning`, `high`, `danger`, `info`, each with a `-soft` background.
- **Other:** a radius scale, `shadow-card` / `shadow-raised` / `shadow-overlay`, and a system font stack with no third-party font requests.

Dark mode is class-based (`.dark` on `<html>`), driven by the theme preference (light, dark or system). Reduced motion is respected.

## 4. State management

| State | Where | Why |
| --- | --- | --- |
| Server data (agents, executions, security, …) | TanStack Query | Caching, loading/error states, invalidation after mutations |
| URL-shareable view state (filters, tabs, sort) | URL search params | Survives reload, shareable, back button works |
| Form state | React Hook Form + Zod | Validation, accessible errors |
| Local UI (dialogs, view toggle, draft tag input) | `useState` | Not shared |
| Theme, sidebar collapsed | Zustand `uiStore` (persisted to localStorage) | Shared across shell and settings |
| Toast queue | Zustand `toastStore` | Raised anywhere, rendered once by the shell |

The current user is fetched through `authService.currentUser()` with TanStack Query.
It is a **demo placeholder**, not a session, and nothing in the frontend is an
authorization control.

## 5. API abstraction

- **Contracts:** `services/contracts.ts` defines `AgentService`, `MarketplaceService`, `ExecutionService`, `SecurityService`, `SystemService`, `AnalyticsService` and `AuthService`. Inputs such as `AgentDraft` and `ProfileUpdate` are typed there.
- **Demo implementation:** `services/demo/createDemoServices.ts` implements every contract in memory. It simulates latency (350 ms; tests use 0), supports create/update/delete/status/execute-request mutations, and returns deep copies so the UI cannot mutate the store.
- **HTTP client:** `services/http/client.ts` is the single `fetch` wrapper.
  - Resolves paths against `VITE_API_BASE_URL` and rejects relative or protocol-relative paths.
  - Sends no `Authorization` header and uses `credentials: 'same-origin'`.
  - Applies a 10 s timeout (configurable).
  - Validates every response with a Zod schema.
  - Throws a typed `ApiError` (`network_error`, `http_<status>`, `invalid_json`, `invalid_response`).

- **HTTP implementation (Phase 2):** `services/http/agentApi.ts` and
  `executionApi.ts` implement `AgentService` and `ExecutionService` against
  `/api/v1`, with response schemas in `services/http/schemas.ts` typed as
  `z.ZodType<Agent>` so a schema that drifts from the domain type fails the build.
  A 404 on a detail request becomes `null`; other failures raise `ApiError`
  carrying the backend's own `code` and `message`.

### Sessions and roles (Phase 3)

`AuthService` owns identity: `session()`, `login()`, `logout()`, `changePassword()`,
`updateProfile()` and `switchOrganization()`. The session is the app's only source
of truth about who is signed in, and it always comes from the server — the
browser holds an HttpOnly cookie it cannot read.

- **Route guard:** every route inside the shell is wrapped in `RequireAuth`, which
  shows the sign-in page when `session()` answers null. `/login` is the only route
  outside it.
- **A 401 anywhere signs the app out:** the query client watches every query and
  mutation, and drops the cached session when the API returns 401, so an expired
  session ends at the sign-in page rather than in a retry loop.
- **CSRF:** `services/http/client.ts` reads the readable `agenthub_csrf` cookie and
  echoes it in `X-CSRF-Token` on every unsafe request.
- **Role-aware UI:** `services/permissions.ts` mirrors the backend matrix, and
  `usePermission()` / `useAgentPermissions()` hide controls a role cannot use.
  This is presentation only — see §9.
- **Demo mode** keeps working without a backend: its `login()` accepts anything and
  the sign-in page says so in as many words.

### Data source

`createServices(dataSource)` returns either the demo services or
`createHttpServices()`. The starting value comes from `VITE_DATA_SOURCE` and the
user can switch it in **Settings → API**; the choice is persisted per browser in
`stores/dataSourceStore.ts`. Switching rebuilds the services **and** the query
cache, so demo rows can never be displayed as backend data.

In API mode the backend serves identity (sessions, members), agents, executions
and the dashboard counts derived from them. Marketplace, security, analytics and the profile still come from demo
data. `services.liveResources` states exactly which resources are real, and
`useIsLive(resource)` drives the `DataNotice` on each page, so no page can keep
claiming "demonstration data" while reading from the backend.

## 6. Mock data

- **Location:** all demonstration data lives in `src/features/demo/`: agents, executions (plus a deterministic detail builder), marketplace listings, security events and policies, system status and analytics series, and fictional people.
- **Labelling:**
  - Each file starts with a *DEMO DATA* comment.
  - Pages that show it carry a `DemoNotice` or `DemoBadge`.
  - Invented figures are named accordingly: `demoUsageCount`, "demo ratings", "Security rating (demo)".
- **Timestamps** are generated relative to page load, so the demo looks recent without claiming real events.
- **Access:** only `src/services/demo/**` and tests may import demo data (ESLint rule).

## 7. Environment variables

Defined in `frontend/.env.example`. Only `VITE_*` variables reach the browser, so they
must never contain secrets.

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | empty | Backend base URL without trailing slash. Empty means same-origin; the Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Validated to be empty or `http(s)`. |
| `VITE_DATA_SOURCE` | `demo` | `demo` or `api`. Which services the app starts with; a user's choice in Settings overrides it for that browser. |

The backend's `.env` (repository root) is **not** read by the frontend.

## 8. Testing

- **Stack:** Vitest (jsdom), Testing Library and user-event. Setup: `src/test/setup.ts`. It includes polyfills for `HTMLDialogElement.showModal/close` and `matchMedia`, which jsdom lacks, and a desktop-width media query default.
- **Harness:** `src/test/renderApp.tsx` renders the real route table in a memory router with fresh demo services at zero latency. Tests can override individual service methods to simulate slow or failing APIs.
- **Coverage areas:**

| Area | Test file |
| --- | --- |
| App shell rendering and navigation (sidebar, redirect, mobile drawer) | `app/App.test.tsx` |
| Dashboard | `features/dashboard/DashboardPage.test.tsx` |
| Agent list: filters, sorting, delete confirmation, disabled execute | `features/agents/AgentsPage.test.tsx` |
| Agent details and not-found | `features/agents/AgentDetailPage.test.tsx` |
| Create-agent validation (required, invalid values, invalid configuration, success) | `features/agents/CreateAgentPage.test.tsx`, `features/agents/form/schema.test.ts` |
| Execution status rendering, list filter, detail view | `features/executions/Executions.test.tsx` |
| Security dashboard | `features/security/SecurityPage.test.tsx` |
| 404 page and route error boundary | `features/errors/Errors.test.tsx` |
| Loading and error states (including retry) | `features/QueryStates.test.tsx` |
| HTTP client and environment configuration | `services/http/client.test.ts` |

Run from `frontend/`:

```powershell
npm test            # vitest run
npm run lint
npm run typecheck
npm run build
```

## 9. Security notes

- No secrets, API keys or credentials exist in frontend code or `.env.example`.
- The API key field in Settings is a masked placeholder and never holds a real value.
- Frontend permissions, risk estimates (`lib/risk.ts`) and disabled buttons are **UX only**. Authorization will be enforced by the backend (Phase 3), and permissions by the tool gateway and policy engine (later phases).
- Raw HTML rendering is banned by lint (`dangerouslySetInnerHTML`), and `eval`-style APIs are errors.
- API responses are validated at runtime before use.
- Error UI never shows raw error messages or stack traces from thrown values.

## 10. Known limitations

- **Data and backend:**
  - All data is demonstration data held in memory; changes are lost on reload.
  - No backend integration beyond the health check; no persistence.
  - No authentication, sessions or authorization; the "current user" is a placeholder.
- **Not yet real:**
  - No real agent execution: "Execute" queues an in-memory record, and "Deploy" only explains that deployment is unavailable.
  - No real security scanning, detection or policy enforcement.
  - Logs and timelines are generated and not real-time.
  - Notification and agent preference settings are not saved.
- **Frontend gaps:**
  - No pagination: demo datasets are small, and real APIs will need server-side pagination.
  - UI text is English only.
  - Vendor code is split into stable chunks (`vendor-react`, `vendor-forms`, `vendor-data`, `vendor-icons`); the largest is about 311 kB minified (98 kB gzipped).
  - Keyboard and screen-reader behaviour is covered by semantic markup and tests, but has not yet been audited with real assistive technology.
