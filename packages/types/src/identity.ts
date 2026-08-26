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

export interface StoreIdentityVerifier {
  readonly kind: StoreIdentityKind;
  verifyMerchantSession(payload: unknown): Promise<MerchantSessionResult>;
  verifyShopperSession?(token: string, tenantId: string): Promise<ShopperSessionResult>;
}
