export interface MetaOAuthExchangeResult {
  ok: boolean;
  accessToken?: string;
  wabaId?: string;
  phoneNumberId?: string;
  displayPhoneNumber?: string;
  error?: string;
}

export interface EmbeddedSignupConfig {
  appId: string;
  appSecret: string;
  configId?: string;
  graphApiVersion?: string;
  fetchFn?: typeof fetch;
}

export class MetaEmbeddedSignupService {
  private appId: string;
  private appSecret: string;
  private configId?: string;
  private graphApiVersion: string;
  private fetchFn: typeof fetch;

  constructor(options?: Partial<EmbeddedSignupConfig>) {
    this.appId = options?.appId || process.env.META_APP_ID || '1584644373301704';
    this.appSecret = options?.appSecret || process.env.META_APP_SECRET || '';
    this.configId = options?.configId || process.env.META_EMBEDDED_CONFIG_ID;
    this.graphApiVersion = options?.graphApiVersion || 'v21.0';
    this.fetchFn = options?.fetchFn || globalThis.fetch;
  }

  /**
   * Returns configuration required by the frontend Meta Embedded Signup SDK popup.
   */
  getFrontendConfig(tenantId: string): { appId: string; configId?: string; version: string; state: string } {
    return {
      appId: this.appId,
      configId: this.configId,
      version: this.graphApiVersion,
      state: tenantId
    };
  }

  /**
   * Exchanges the temporary OAuth code from the Meta Embedded Signup popup for an access token,
   * fetches the registered Phone Number ID, and subscribes our app to their WABA webhooks.
   */
  async exchangeCodeAndProvisionWaba(options: {
    code: string;
    wabaId?: string;
    phoneNumberId?: string;
  }): Promise<MetaOAuthExchangeResult> {
    if (!this.appSecret) {
      return { ok: false, error: 'META_APP_SECRET is not configured on server.' };
    }

    // 1. Exchange OAuth code for Access Token
    const tokenUrl = `https://graph.facebook.com/${this.graphApiVersion}/oauth/access_token` +
      `?client_id=${encodeURIComponent(this.appId)}` +
      `&client_secret=${encodeURIComponent(this.appSecret)}` +
      `&code=${encodeURIComponent(options.code)}`;

    try {
      const tokenRes = await this.fetchFn(tokenUrl, { method: 'GET' });
      if (!tokenRes.ok) {
        const errJson = await tokenRes.json().catch(() => ({}));
        return { ok: false, error: `Meta OAuth exchange failed: ${tokenRes.status} ${JSON.stringify(errJson)}` };
      }

      const tokenData = (await tokenRes.json()) as { access_token?: string };
      const accessToken = tokenData.access_token;
      if (!accessToken) {
        return { ok: false, error: 'No access token returned from Meta OAuth exchange.' };
      }

      let wabaId = options.wabaId;
      let phoneNumberId = options.phoneNumberId;
      let displayPhoneNumber: string | undefined;

      // 2. If WABA ID or Phone Number ID wasn't provided in callback, query debug_token / waba phone numbers
      if (!wabaId || !phoneNumberId) {
        const debugUrl = `https://graph.facebook.com/${this.graphApiVersion}/debug_token` +
          `?input_token=${encodeURIComponent(accessToken)}` +
          `&access_token=${encodeURIComponent(`${this.appId}|${this.appSecret}`)}`;

        const debugRes = await this.fetchFn(debugUrl, { method: 'GET' });
        if (debugRes.ok) {
          const debugData = (await debugRes.json()) as { data?: { granular_scopes?: Array<{ target_ids?: string[] }> } };
          const targetIds = debugData?.data?.granular_scopes?.[0]?.target_ids;
          if (targetIds && targetIds[0]) {
            wabaId = targetIds[0];
          }
        }
      }

      // 3. Query phone numbers under the WABA
      if (wabaId && !phoneNumberId) {
        const phoneUrl = `https://graph.facebook.com/${this.graphApiVersion}/${wabaId}/phone_numbers`;
        const phoneRes = await this.fetchFn(phoneUrl, {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (phoneRes.ok) {
          const phoneData = (await phoneRes.json()) as { data?: Array<{ id: string; display_phone_number: string }> };
          if (phoneData?.data?.[0]) {
            phoneNumberId = phoneData.data[0].id;
            displayPhoneNumber = phoneData.data[0].display_phone_number;
          }
        }
      }

      // 4. Automatically Subscribe our Webhook to the client's WABA
      if (wabaId) {
        const subUrl = `https://graph.facebook.com/${this.graphApiVersion}/${wabaId}/subscribed_apps`;
        await this.fetchFn(subUrl, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          }
        }).catch(() => null);
      }

      return {
        ok: true,
        accessToken,
        wabaId,
        phoneNumberId,
        displayPhoneNumber
      };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }
}
