import { z } from 'zod';

export const StoreIdentityKindSchema = z.enum([
  'estore_jwt',
  'woocommerce_oauth',
  'shopify_oauth',
  'magic_link'
]);
export type StoreIdentityKind = z.infer<typeof StoreIdentityKindSchema>;

export const MerchantSessionResultSchema = z.object({
  ok: z.boolean(),
  tenantId: z.string().uuid(),
  ownerEmail: z.string().email(),
  sellerId: z.string().optional(),
  roles: z.array(z.string()).optional()
});
export type MerchantSessionResult = z.infer<typeof MerchantSessionResultSchema>;

export const ShopperSessionResultSchema = z
  .object({
    customerId: z.string().min(1),
    email: z.string().email().optional(),
    name: z.string().optional()
  })
  .nullable();
export type ShopperSessionResult = z.infer<typeof ShopperSessionResultSchema>;

export const UserRoleSchema = z.enum(['owner', 'agent', 'viewer']);
export type UserRole = z.infer<typeof UserRoleSchema>;

export const PlatformUserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().nullable().optional(),
  createdAt: z.string().datetime().optional(),
  updatedAt: z.string().datetime().optional()
});
export type PlatformUser = z.infer<typeof PlatformUserSchema>;

export const TenantMembershipSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  userId: z.string().uuid(),
  role: UserRoleSchema,
  createdAt: z.string().datetime().optional()
});
export type TenantMembership = z.infer<typeof TenantMembershipSchema>;

export interface StoreIdentityVerifier {
  readonly kind: StoreIdentityKind;
  verifyMerchantSession(payload: unknown): Promise<MerchantSessionResult>;
  verifyShopperSession?(token: string, tenantId: string): Promise<ShopperSessionResult>;
}

