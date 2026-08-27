export interface WabaRegisterOptions {
  phoneNumberId: string;
  pin: string; // 6-digit PIN for two-step verification
  accessToken?: string;
  fetchFn?: typeof fetch;
}

export interface WabaStatusOptions {
  phoneNumberId: string;
  accessToken?: string;
  fetchFn?: typeof fetch;
}

export interface WabaPhoneNumberStatus {
  id: string;
  verifiedName: string;
  displayPhoneNumber: string;
  qualityRating: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  status: 'CONNECTED' | 'PENDING' | 'DISCONNECTED' | 'FLAGGED';
  codeVerificationStatus: 'VERIFIED' | 'EXPIRED' | 'NOT_VERIFIED';
}

export class WabaOnboardingService {
  private defaultAccessToken?: string;
  private graphApiVersion: string;
  private fetchFn: typeof fetch;

  constructor(options?: { accessToken?: string; graphApiVersion?: string; fetchFn?: typeof fetch }) {
    this.defaultAccessToken = options?.accessToken || process.env.WHATSAPP_ACCESS_TOKEN;
    this.graphApiVersion = options?.graphApiVersion || 'v21.0';
    this.fetchFn = options?.fetchFn || globalThis.fetch;
  }

  async registerPhoneNumber(options: WabaRegisterOptions): Promise<{ ok: boolean; error?: string }> {
    const token = options.accessToken || this.defaultAccessToken;
    if (!token) {
      return { ok: false, error: 'Access token is required to register phone number' };
    }

    const url = `https://graph.facebook.com/${this.graphApiVersion}/${options.phoneNumberId}/register`;
    const payload = {
      messaging_product: 'whatsapp',
      pin: options.pin
    };

    try {
      const res = await (options.fetchFn || this.fetchFn)(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Failed to register phone number: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as { success?: boolean };
      return { ok: !!data.success };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }

  async getPhoneNumberStatus(options: WabaStatusOptions): Promise<{ ok: boolean; status?: WabaPhoneNumberStatus; error?: string }> {
    const token = options.accessToken || this.defaultAccessToken;
    if (!token) {
      return { ok: false, error: 'Access token is required to check status' };
    }

    const url = `https://graph.facebook.com/${this.graphApiVersion}/${options.phoneNumberId}?fields=verified_name,display_phone_number,quality_rating,status,code_verification_status`;

    try {
      const res = await (options.fetchFn || this.fetchFn)(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Failed to get status: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as {
        id: string;
        verified_name?: string;
        display_phone_number?: string;
        quality_rating?: 'GREEN' | 'YELLOW' | 'RED';
        status?: 'CONNECTED' | 'PENDING' | 'DISCONNECTED' | 'FLAGGED';
        code_verification_status?: 'VERIFIED' | 'EXPIRED' | 'NOT_VERIFIED';
      };

      return {
        ok: true,
        status: {
          id: data.id,
          verifiedName: data.verified_name || '',
          displayPhoneNumber: data.display_phone_number || '',
          qualityRating: data.quality_rating || 'UNKNOWN',
          status: data.status || 'CONNECTED',
          codeVerificationStatus: data.code_verification_status || 'VERIFIED'
        }
      };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }
}
