import React, { useState } from 'react';

export interface MerchantOnboardingState {
  businessName: string;
  verticalPack: 'swiss_cleaning' | 'hvac_trades' | 'ecommerce_retail';
  country: string;
  defaultLanguage: 'de' | 'fr' | 'it' | 'en';
  ownerPhone: string;
  wabaId: string;
  phoneNumberId: string;
  accessToken: string;
  baseRateChf: number;
}

export function MerchantOnboardingWizard(props: {
  initialState?: Partial<MerchantOnboardingState>;
  onComplete?: (state: MerchantOnboardingState) => void;
}) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [state, setState] = useState<MerchantOnboardingState>({
    businessName: props.initialState?.businessName || '',
    verticalPack: props.initialState?.verticalPack || 'swiss_cleaning',
    country: props.initialState?.country || 'CH',
    defaultLanguage: props.initialState?.defaultLanguage || 'de',
    ownerPhone: props.initialState?.ownerPhone || '+41',
    wabaId: props.initialState?.wabaId || '',
    phoneNumberId: props.initialState?.phoneNumberId || '',
    accessToken: props.initialState?.accessToken || '',
    baseRateChf: props.initialState?.baseRateChf || 650
  });

  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch('/api/waba/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phoneNumberId: state.phoneNumberId,
          accessToken: state.accessToken
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setTestResult(`✅ WhatsApp Connected: ${data.status?.displayPhoneNumber || 'Ready'} (${data.status?.status || 'CONNECTED'})`);
      } else {
        setTestResult(`❌ Connection Failed: ${data.error || 'Check Phone ID and Token'}`);
      }
    } catch {
      setTestResult('❌ Network error during WhatsApp health check.');
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: '40px auto', fontFamily: 'system-ui, -apple-system, sans-serif', color: '#0f172a' }}>
      {/* Progress Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 32, borderBottom: '1px solid #e2e8f0', paddingBottom: 16 }}>
        <div style={{ fontWeight: step === 1 ? 700 : 500, color: step === 1 ? '#0284c7' : '#64748b' }}>1. Business Profile</div>
        <div style={{ fontWeight: step === 2 ? 700 : 500, color: step === 2 ? '#0284c7' : '#64748b' }}>2. Trade Vertical Pack</div>
        <div style={{ fontWeight: step === 3 ? 700 : 500, color: step === 3 ? '#0284c7' : '#64748b' }}>3. WhatsApp API Connect</div>
        <div style={{ fontWeight: step === 4 ? 700 : 500, color: step === 4 ? '#0284c7' : '#64748b' }}>4. Launch & Self-Test</div>
      </div>

      {/* Step 1: Business Profile */}
      {step === 1 && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 32 }}>
          <h2 style={{ fontSize: 24, marginTop: 0 }}>Step 1: Your Business Profile</h2>
          <p style={{ color: '#64748b', fontSize: 14 }}>Enter your company details for quotes and Swiss compliance (revDSG/GDPR).</p>

          <div style={{ marginTop: 24 }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Business Name</label>
            <input
              type="text"
              placeholder="e.g. Zürich Clean Pro GmbH"
              value={state.businessName}
              onChange={(e) => setState({ ...state, businessName: e.target.value })}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
            />
          </div>

          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Owner WhatsApp Mobile (for 1-tap quote confirmations)</label>
            <input
              type="text"
              placeholder="+41 79 123 45 67"
              value={state.ownerPhone}
              onChange={(e) => setState({ ...state, ownerPhone: e.target.value })}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
            />
          </div>

          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Country</label>
              <select
                value={state.country}
                onChange={(e) => setState({ ...state, country: e.target.value })}
                style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
              >
                <option value="CH">Switzerland (CHF)</option>
                <option value="DE">Germany (EUR)</option>
                <option value="AT">Austria (EUR)</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Default Language</label>
              <select
                value={state.defaultLanguage}
                onChange={(e) => setState({ ...state, defaultLanguage: e.target.value as any })}
                style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
              >
                <option value="de">German / Swiss German (Mundart)</option>
                <option value="fr">French (Français)</option>
                <option value="it">Italian (Italiano)</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          <button
            onClick={() => setStep(2)}
            disabled={!state.businessName || !state.ownerPhone}
            style={{
              marginTop: 32,
              width: '100%',
              padding: '12px 20px',
              borderRadius: 8,
              background: '#0284c7',
              color: '#fff',
              fontWeight: 600,
              fontSize: 16,
              border: 'none',
              cursor: 'pointer'
            }}
          >
            Continue to Vertical Pack →
          </button>
        </div>
      )}

      {/* Step 2: Trade Vertical Pack */}
      {step === 2 && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 32 }}>
          <h2 style={{ fontSize: 24, marginTop: 0 }}>Step 2: Select AI Vertical Pack</h2>
          <p style={{ color: '#64748b', fontSize: 14 }}>Choose the trade formula and extraction parameters for your industry.</p>

          <div style={{ display: 'grid', gap: 16, marginTop: 24 }}>
            <div
              onClick={() => setState({ ...state, verticalPack: 'swiss_cleaning', baseRateChf: 650 })}
              style={{
                border: state.verticalPack === 'swiss_cleaning' ? '2px solid #0284c7' : '1px solid #cbd5e1',
                borderRadius: 10,
                padding: 20,
                cursor: 'pointer',
                background: state.verticalPack === 'swiss_cleaning' ? '#f0f9ff' : '#fff'
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 16 }}>🇨🇭 Swiss Cleaning & Umzugsreinigung Pack</div>
              <div style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
                Extracts $m^2$, room counts (1.5R–5.5R), Abnahmegarantie, balconies, and blinds with formula-grounded pricing.
              </div>
            </div>

            <div
              onClick={() => setState({ ...state, verticalPack: 'hvac_trades', baseRateChf: 250 })}
              style={{
                border: state.verticalPack === 'hvac_trades' ? '2px solid #0284c7' : '1px solid #cbd5e1',
                borderRadius: 10,
                padding: 20,
                cursor: 'pointer',
                background: state.verticalPack === 'hvac_trades' ? '#f0f9ff' : '#fff'
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 16 }}>🛠️ HVAC, Plumbing & Handwerker Notfall Pack</div>
              <div style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
                Emergency 24/7 dispatch rate calculation, location extraction, and urgency triage.
              </div>
            </div>

            <div
              onClick={() => setState({ ...state, verticalPack: 'ecommerce_retail', baseRateChf: 0 })}
              style={{
                border: state.verticalPack === 'ecommerce_retail' ? '2px solid #0284c7' : '1px solid #cbd5e1',
                borderRadius: 10,
                padding: 20,
                cursor: 'pointer',
                background: state.verticalPack === 'ecommerce_retail' ? '#f0f9ff' : '#fff'
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 16 }}>🛍️ E-Commerce & Retail Store Pack</div>
              <div style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
                Shopify / WooCommerce sync, order drafting, and 1-click Stripe checkout links in chat.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
            <button onClick={() => setStep(1)} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontWeight: 600, cursor: 'pointer' }}>← Back</button>
            <button onClick={() => setStep(3)} style={{ flex: 2, padding: 12, borderRadius: 8, background: '#0284c7', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}>Continue to WhatsApp Connect →</button>
          </div>
        </div>
      )}

      {/* Step 3: WhatsApp API Connect */}
      {step === 3 && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 32 }}>
          <h2 style={{ fontSize: 24, marginTop: 0 }}>Step 3: Connect WhatsApp Business API</h2>
          <p style={{ color: '#64748b', fontSize: 14 }}>Connect via Meta Embedded Signup popup or enter your Cloud API credentials.</p>

          <button
            onClick={() => {
              if (typeof window !== 'undefined' && (window as any).FB) {
                (window as any).FB.login((response: any) => {
                  if (response.authResponse?.code) {
                    fetch('/api/waba/embedded-signup/callback', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ code: response.authResponse.code, tenantId: state.businessName })
                    })
                      .then((r) => r.json())
                      .then((data) => {
                        if (data.ok) {
                          setState((prev) => ({
                            ...prev,
                            wabaId: data.wabaId || prev.wabaId,
                            phoneNumberId: data.phoneNumberId || prev.phoneNumberId,
                            accessToken: data.accessToken || prev.accessToken
                          }));
                          setStep(4);
                        }
                      });
                  }
                }, {
                  config_id: '1584644373301704',
                  response_type: 'code',
                  override_default_response_type: true,
                  extras: { setup: {}, featureType: '', sessionInfoVersion: '2' }
                });
              } else {
                alert('Meta SDK loading. You can also enter credentials directly below.');
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              width: '100%',
              padding: '14px 20px',
              borderRadius: 8,
              background: '#1877f2',
              color: '#fff',
              fontWeight: 700,
              fontSize: 16,
              border: 'none',
              cursor: 'pointer',
              marginTop: 20
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
            </svg>
            1-Click Meta Embedded Signup (Connect WhatsApp)
          </button>

          <div style={{ textAlign: 'center', margin: '20px 0', color: '#94a3b8', fontSize: 13 }}>— or enter credentials directly —</div>

          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Phone Number ID</label>
            <input
              type="text"
              placeholder="e.g. 104829384729182"
              value={state.phoneNumberId}
              onChange={(e) => setState({ ...state, phoneNumberId: e.target.value })}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
            />
          </div>

          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>WABA ID (WhatsApp Business Account ID)</label>
            <input
              type="text"
              placeholder="e.g. 1406719968069623"
              value={state.wabaId}
              onChange={(e) => setState({ ...state, wabaId: e.target.value })}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
            />
          </div>

          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Access Token / System User Token</label>
            <input
              type="password"
              placeholder="EAA..."
              value={state.accessToken}
              onChange={(e) => setState({ ...state, accessToken: e.target.value })}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15 }}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
            <button onClick={() => setStep(2)} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontWeight: 600, cursor: 'pointer' }}>← Back</button>
            <button onClick={() => setStep(4)} style={{ flex: 2, padding: 12, borderRadius: 8, background: '#0284c7', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}>Review & Launch →</button>
          </div>
        </div>
      )}

      {/* Step 4: Review, Health Check & Launch */}
      {step === 4 && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 32 }}>
          <h2 style={{ fontSize: 24, marginTop: 0 }}>Step 4: Launch & Self-Test</h2>
          <p style={{ color: '#64748b', fontSize: 14 }}>Verify your WhatsApp Cloud API connection before going live.</p>

          <div style={{ background: '#f8fafc', borderRadius: 8, padding: 16, marginTop: 16, fontSize: 14 }}>
            <div><strong>Business:</strong> {state.businessName}</div>
            <div style={{ marginTop: 4 }}><strong>Vertical:</strong> {state.verticalPack}</div>
            <div style={{ marginTop: 4 }}><strong>Owner Mobile:</strong> {state.ownerPhone}</div>
            <div style={{ marginTop: 4 }}><strong>Phone Number ID:</strong> {state.phoneNumberId || 'Pending'}</div>
          </div>

          <div style={{ marginTop: 24 }}>
            <button
              onClick={handleTestConnection}
              disabled={isTesting || !state.phoneNumberId || !state.accessToken}
              style={{
                padding: '10px 18px',
                borderRadius: 8,
                background: '#0f172a',
                color: '#fff',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer'
              }}
            >
              {isTesting ? 'Verifying with Meta...' : '⚡ Test WhatsApp Connection'}
            </button>
            {testResult && (
              <div style={{ marginTop: 12, fontSize: 14, fontWeight: 600 }}>{testResult}</div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
            <button onClick={() => setStep(3)} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontWeight: 600, cursor: 'pointer' }}>← Back</button>
            <button
              onClick={() => props.onComplete?.(state)}
              style={{
                flex: 2,
                padding: 12,
                borderRadius: 8,
                background: '#16a34a',
                color: '#fff',
                border: 'none',
                fontWeight: 700,
                fontSize: 16,
                cursor: 'pointer'
              }}
            >
              🚀 Activate Commercial Pipeline
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
