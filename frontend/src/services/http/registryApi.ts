import { z } from 'zod';
import type {
  InstallationPatch,
  InstallationService,
  InstallInput,
  MarketplaceParams,
  MarketplaceService,
  PublishInput,
} from '@/services/contracts';
import type {
  AgentVersion,
  ID,
  Installation,
  InstallationDetail,
  MarketplaceListing,
  MarketplaceListingDetail,
  Visibility,
} from '@/types/domain';
import { apiRequest, apiRequestVoid } from './client';
import { orNull } from './orNull';
import { AgentSchema, PermissionSchema, pageSchema } from './schemas';

/** Versions, the marketplace and installations, served by `/api/v1`. */

const PAGE_LIMIT = 200;

const category = z.enum([
  'research',
  'security',
  'engineering',
  'data',
  'operations',
  'support',
  'marketing',
]);
const riskLevel = z.enum(['low', 'medium', 'high', 'critical']);
const visibility = z.enum(['private', 'organization', 'public']);
const verification = z.enum(['verified', 'pending', 'unverified', 'rejected']);

const ManifestSchema = z.object({
  name: z.string(),
  description: z.string(),
  category,
  tags: z.array(z.string()),
  version: z.string(),
  model: z.object({
    provider: z.string(),
    model: z.string(),
    temperature: z.number(),
    maxOutputTokens: z.number(),
  }),
  tools: z.array(z.string()),
  requiredPermissions: z.array(PermissionSchema),
  resourceLimits: z.object({
    maxRuntimeSeconds: z.number(),
    maxMemoryMb: z.number(),
    maxTokensPerRun: z.number(),
    maxToolCalls: z.number(),
  }),
  securityPolicy: z.object({
    sandbox: z.enum(['strict', 'standard']),
    networkEgress: z.enum(['none', 'allow_list']),
    allowedDomains: z.array(z.string()),
    approvalRequiredFor: z.array(riskLevel),
    auditLogging: z.boolean(),
  }),
});

const VersionSchema: z.ZodType<AgentVersion> = z.object({
  id: z.string(),
  agentId: z.string(),
  version: z.string(),
  status: z.enum(['draft', 'published', 'deprecated']),
  riskLevel,
  riskScore: z.number(),
  changelog: z.array(z.string()),
  manifest: ManifestSchema,
  createdAt: z.string(),
  publishedAt: z.string().nullable(),
  deprecatedAt: z.string().nullable(),
  createdBy: z.string(),
});

const ListingShape = {
  id: z.string(),
  agentId: z.string(),
  name: z.string(),
  summary: z.string(),
  category,
  tags: z.array(z.string()),
  version: z.string(),
  publisher: z.string(),
  verification,
  visibility,
  riskLevel,
  riskScore: z.number(),
  tools: z.array(z.string()),
  publishedAt: z.string(),
  installed: z.boolean(),
  installationId: z.string().nullable(),
  own: z.boolean(),
};

const ListingSchema: z.ZodType<MarketplaceListing> = z.object(ListingShape);
const ListingDetailSchema: z.ZodType<MarketplaceListingDetail> = z.object({
  ...ListingShape,
  manifest: ManifestSchema,
  changelog: z.array(z.string()),
});

const InstallationShape = {
  id: z.string(),
  agentId: z.string(),
  agentVersionId: z.string(),
  agentName: z.string(),
  publisher: z.string(),
  version: z.string(),
  status: z.enum(['active', 'suspended']),
  grants: z.array(PermissionSchema),
  riskLevel,
  riskScore: z.number(),
  note: z.string().nullable(),
  installedBy: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  unusableTools: z.array(z.string()),
  updateAvailable: z.boolean(),
};

const InstallationSchema: z.ZodType<Installation> = z.object(InstallationShape);
const InstallationDetailSchema: z.ZodType<InstallationDetail> = z.object({
  ...InstallationShape,
  manifest: ManifestSchema,
});

const VersionPageSchema = pageSchema(VersionSchema);
const ListingPageSchema = pageSchema(ListingSchema);
const InstallationPageSchema = pageSchema(InstallationSchema);

export async function fetchVersions(agentId: ID): Promise<AgentVersion[]> {
  const page = await apiRequest(
    `/api/v1/agents/${encodeURIComponent(agentId)}/versions?limit=${PAGE_LIMIT}`,
    VersionPageSchema,
  );
  return page.items;
}

export function publishVersion(agentId: ID, input: PublishInput): Promise<AgentVersion> {
  return apiRequest(`/api/v1/agents/${encodeURIComponent(agentId)}/versions`, VersionSchema, {
    method: 'POST',
    body: input,
  });
}

export function setAgentVisibility(agentId: ID, value: Visibility) {
  return apiRequest(`/api/v1/agents/${encodeURIComponent(agentId)}/visibility`, AgentSchema, {
    method: 'PATCH',
    body: { visibility: value },
  });
}

function listingQuery(params: MarketplaceParams): string {
  const query = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  const search = params.search?.trim();
  if (search) query.set('search', search);
  if (params.category && params.category !== 'all') query.set('category', params.category);
  if (params.tag) query.set('tag', params.tag);
  if (params.collection === 'verified') query.set('verified', 'true');
  return query.toString();
}

export const httpMarketplaceService: MarketplaceService = {
  async list(params: MarketplaceParams = {}): Promise<MarketplaceListing[]> {
    const page = await apiRequest(`/api/v1/marketplace?${listingQuery(params)}`, ListingPageSchema);
    // "Installed" is a view over the same listings, so it is filtered here.
    return params.collection === 'installed'
      ? page.items.filter((listing) => listing.installed)
      : page.items;
  },

  get(id: ID): Promise<MarketplaceListingDetail | null> {
    return orNull(apiRequest(`/api/v1/marketplace/${encodeURIComponent(id)}`, ListingDetailSchema));
  },

  tags(): Promise<string[]> {
    return apiRequest('/api/v1/marketplace/tags', z.array(z.string()));
  },
};

export const httpInstallationService: InstallationService = {
  async list(): Promise<Installation[]> {
    const page = await apiRequest(
      `/api/v1/installations?limit=${PAGE_LIMIT}`,
      InstallationPageSchema,
    );
    return page.items;
  },

  get(id: ID): Promise<InstallationDetail | null> {
    return orNull(
      apiRequest(`/api/v1/installations/${encodeURIComponent(id)}`, InstallationDetailSchema),
    );
  },

  install(input: InstallInput): Promise<InstallationDetail> {
    return apiRequest('/api/v1/installations', InstallationDetailSchema, {
      method: 'POST',
      body: input,
    });
  },

  update(id: ID, patch: InstallationPatch): Promise<InstallationDetail> {
    return apiRequest(
      `/api/v1/installations/${encodeURIComponent(id)}`,
      InstallationDetailSchema,
      { method: 'PATCH', body: patch },
    );
  },

  uninstall(id: ID): Promise<void> {
    return apiRequestVoid(`/api/v1/installations/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
};
