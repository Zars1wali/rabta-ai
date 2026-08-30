import React, { useState } from 'react';

export interface ExtractedLeadData {
  intent: 'quote_request' | 'appointment_request' | 'product_enquiry' | 'emergency';
  intentLabel: string;
  customerName: string;
  language: string;
  extractedFields: Record<string, string>;
  completeness: number; // 0 to 100
  missingFields: string[];
  suggestedAction: string;
  aiResponse: string;
}

export interface PresetScenario {
  id: string;
  label: string;
  market: 'trades' | 'ecommerce';
  message: string;
  lead: ExtractedLeadData;
}

export const PRESET_SCENARIOS: PresetScenario[] = [
  {
    id: 'swiss_cleaning',
    label: '🇨🇭 Swiss Cleaning (Mundart / DE)',
    market: 'trades',
    message:
      'Grüezi! Mir bruuched e Endreinigung für e 4.5 Zimmer Wohnig (ca. 115 m²) in 8001 Zürich am 15. Oktober mit Abnahmegarantie.',
    lead: {
      intent: 'quote_request',
      intentLabel: 'Move-Out Deep Clean Quote',
      customerName: 'Thomas Meier',
      language: 'Swiss German → DE (Normalized)',
      extractedFields: {
        'Service Type': 'Move-out deep clean (Endreinigung)',
        'Property Size': '4.5 rooms / ~115 m²',
        'Postal Code & City': '8001 Zürich',
        'Target Date': '15. October 2026',
        'Handover Guarantee': 'Required (Abnahmegarantie)'
      },
      completeness: 90,
      missingFields: ['Access details (Key deposit or on-site presence)'],
      suggestedAction: 'Propose Standard 4.5 Room Package (CHF 1,180.- incl. Guarantee)',
      aiResponse:
        'Grüezi Herr Meier, vielen Dank für Ihre Anfrage! Für eine 4.5-Zimmer-Wohnung (115 m²) in 8001 Zürich mit Abnahmegarantie am 15. Oktober beträgt unser Festpreis gemäss Tarif CHF 1’180.– inkl. MwSt. und Material. Dürfen wir den Termin für Sie reservieren?'
    }
  },
  {
    id: 'emergency_trade',
    label: '🛠️ HVAC / Plumbing Repair (EN)',
    market: 'trades',
    message:
      'Hi, our commercial bakery oven heating circuit tripped and is displaying error E04 in central Zurich. Can someone come inspect today?',
    lead: {
      intent: 'emergency',
      intentLabel: 'Emergency Commercial Repair',
      customerName: 'Bakery Bäckerei Stadelhofen',
      language: 'English (EN)',
      extractedFields: {
        'Equipment Type': 'Commercial Bakery Oven',
        'Reported Fault': 'Heating circuit breaker tripped (Error E04)',
        'Location': 'Zurich City (Central)',
        'Urgency': 'Immediate / Same Day'
      },
      completeness: 85,
      missingFields: ['Equipment Model / Serial number photo'],
      suggestedAction: 'Dispatch Emergency Tech Window (14:00 - 16:00)',
      aiResponse:
        'Hi there, we have flagged this as an urgent priority. Our standard emergency diagnostic fee is CHF 180.-. A technician is available today between 14:00 and 16:00. Would you like to confirm the dispatch?'
    }
  },
  {
    id: 'ecommerce_order',
    label: '🛍️ E-Commerce WhatsApp Checkout (FR)',
    market: 'ecommerce',
    message:
      'Bonjour! Je voudrais commander 2 bouteilles de votre Huile d’Olive Bio 500ml et savoir si vous livrez à Genève d’ici vendredi.',
    lead: {
      intent: 'product_enquiry',
      intentLabel: 'Product Order & Stock Check',
      customerName: 'Claire Dubois',
      language: 'French (FR)',
      extractedFields: {
        'Item SKU': 'BIO-OIL-500ML (In Stock: 48 units)',
        'Quantity': '2 units (CHF 28.00 / unit)',
        'Delivery Location': 'Geneva, Switzerland',
        'Required Deadline': 'Friday (SwissPost Priority)'
      },
      completeness: 95,
      missingFields: ['Shipping Street Address'],
      suggestedAction: 'Draft Stripe 1-Tap Checkout Link (CHF 63.90 incl. Express Shipping)',
      aiResponse:
        'Bonjour Claire! Oui, notre Huile d’Olive Bio 500ml est bien en stock. Pour 2 bouteilles avec livraison prioritaire à Genève avant vendredi, le total est de CHF 63.90. Cliquez ici pour régler en 1 clic: https://nuncio.link/pay/chk_98a7bc'
    }
  }
];

export function parseCustomMessage(text: string): ExtractedLeadData {
  const isCleaning = /clean|reinigung|putzen|zimmer|m2|sqm/i.test(text);
  const isEmergency = /urgent|notfall|leak|broken|repair|kaputt|heute|today/i.test(text);
  const isFrench = /bonjour|merci|commander|svp/i.test(text);
  const isGerman = /grüezi|guten tag|bitte|wohnung|preis/i.test(text);

  let lang = 'English (EN)';
  if (isGerman) lang = 'German (DE)';
  if (isFrench) lang = 'French (FR)';

  if (isCleaning) {
    return {
      intent: 'quote_request',
      intentLabel: 'Trade Service Quote Request',
      customerName: 'Prospective Client',
      language: lang,
      extractedFields: {
        'Service Requested': 'Cleaning / Facility Services',
        'Raw Request': text.slice(0, 80) + (text.length > 80 ? '...' : ''),
        'Classification': 'B2B Trade Inbound',
        'Catalog Verification': 'Matched Verified Offering'
      },
      completeness: 80,
      missingFields: ['Exact address', 'Access code / key status'],
      suggestedAction: 'Review Catalog Rate & Generate Quote',
      aiResponse:
        'Thank you for reaching out! We have received your inquiry. Based on our verified service pricing, a tailored proposal has been drafted for your confirmation.'
    };
  }

  if (isEmergency) {
    return {
      intent: 'emergency',
      intentLabel: 'Urgent Service Dispatch',
      customerName: 'Urgent Client',
      language: lang,
      extractedFields: {
        'Incident Type': 'Emergency Support / Repair',
        'Priority Level': 'High (Immediate Attention)',
        'Extracted Notes': text.slice(0, 80)
      },
      completeness: 75,
      missingFields: ['Exact site address', 'Contact phone number'],
      suggestedAction: 'Notify On-Call Technician',
      aiResponse:
        'We understand this is urgent. Our team has been alerted immediately and is reviewing technician availability in your area.'
    };
  }

  return {
    intent: 'product_enquiry',
    intentLabel: 'Commercial Product / Service Inquiry',
    customerName: 'WhatsApp Contact',
    language: lang,
    extractedFields: {
      'Inquiry Category': 'General Catalog Inquiry',
      'Extracted Details': text.slice(0, 80)
    },
    completeness: 70,
    missingFields: ['Customer address or delivery requirements'],
    suggestedAction: 'Propose Catalog Match',
    aiResponse:
      'Hello! Thank you for contacting us. We have matched your inquiry with our verified product catalog and are ready to assist you.'
  };
}

export function Simulator(): React.ReactElement {
  const defaultScenario = PRESET_SCENARIOS[0] || {
    id: 'default',
    label: 'Default',
    market: 'trades' as const,
    message: 'Hello, I would like to request a quote.',
    lead: {
      intent: 'quote_request' as const,
      intentLabel: 'Quote Request',
      customerName: 'Customer',
      language: 'English (EN)',
      extractedFields: { Service: 'General Inbound' },
      completeness: 80,
      missingFields: [],
      suggestedAction: 'Draft Quote',
      aiResponse: 'Thank you for your message!'
    }
  };

  const [selectedPresetId, setSelectedPresetId] = useState<string>(defaultScenario.id);
  const [customText, setCustomText] = useState<string>(defaultScenario.message);
  const [activeLead, setActiveLead] = useState<ExtractedLeadData>(defaultScenario.lead);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const handleSelectPreset = (scenario: PresetScenario) => {
    setSelectedPresetId(scenario.id);
    setCustomText(scenario.message);
    setIsProcessing(true);
    setTimeout(() => {
      setActiveLead(scenario.lead);
      setIsProcessing(false);
    }, 250);
  };

  const handleCustomChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setCustomText(val);
    setSelectedPresetId('custom');
    setIsProcessing(true);
    setTimeout(() => {
      setActiveLead(parseCustomMessage(val));
      setIsProcessing(false);
    }, 200);
  };

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.1)',
        padding: '28px',
        color: '#f8fafc',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
      }}
    >
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <span
            style={{
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              fontSize: '12px',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: '20px',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}
          >
            Live WhatsApp-to-Lead Simulator
          </span>
          <h3 style={{ margin: '8px 0 4px 0', fontSize: '20px', fontWeight: 700 }}>
            Test Real-Time Customer Inbound Parsing
          </h3>
          <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8' }}>
            Choose a live scenario or type custom text in any language / Swiss dialect.
          </p>
        </div>

        {/* Preset Selector Buttons */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {PRESET_SCENARIOS.map((sc) => (
            <button
              key={sc.id}
              onClick={() => handleSelectPreset(sc)}
              style={{
                background: selectedPresetId === sc.id ? '#059669' : 'rgba(255,255,255,0.06)',
                color: '#fff',
                border: selectedPresetId === sc.id ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.1)',
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {sc.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Left Column: WhatsApp Chat Bubble Simulation */}
        <div
          style={{
            background: '#0b141a',
            borderRadius: '12px',
            border: '1px solid #222e35',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              background: '#202c33',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              borderBottom: '1px solid #2a3942'
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: '#00a884',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: '15px'
              }}
            >
              {activeLead.customerName.charAt(0)}
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#e9edef' }}>{activeLead.customerName}</div>
              <div style={{ fontSize: '11px', color: '#8696a0' }}>Online • WhatsApp Business Channel</div>
            </div>
          </div>

          <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Customer Message Bubble */}
            <div style={{ alignSelf: 'flex-start', maxWidth: '85%' }}>
              <div
                style={{
                  background: '#202c33',
                  color: '#e9edef',
                  padding: '10px 14px',
                  borderRadius: '0 12px 12px 12px',
                  fontSize: '13.5px',
                  lineHeight: '1.45',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
                }}
              >
                {customText}
              </div>
              <span style={{ fontSize: '10px', color: '#8696a0', marginTop: '4px', display: 'block' }}>10:42 AM</span>
            </div>

            {/* AI Automated Draft Response Bubble */}
            <div style={{ alignSelf: 'flex-end', maxWidth: '85%' }}>
              <div
                style={{
                  background: '#005c4b',
                  color: '#e9edef',
                  padding: '10px 14px',
                  borderRadius: '12px 0 12px 12px',
                  fontSize: '13.5px',
                  lineHeight: '1.45',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
                  opacity: isProcessing ? 0.6 : 1
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#25d366', marginBottom: '4px' }}>
                  🤖 Nuncio Grounded Assistant (Instant &lt; 1 min)
                </div>
                {activeLead.aiResponse}
              </div>
              <span style={{ fontSize: '10px', color: '#8696a0', marginTop: '4px', textAlign: 'right', display: 'block' }}>
                10:42 AM • ✓✓ Delivered
              </span>
            </div>
          </div>

          {/* Text Area for Live Typing */}
          <div style={{ padding: '12px', background: '#202c33', borderTop: '1px solid #2a3942' }}>
            <label htmlFor="custom-input" style={{ fontSize: '11px', color: '#8696a0', marginBottom: '4px', display: 'block' }}>
              Type your own customer message to test parser:
            </label>
            <textarea
              id="custom-input"
              value={customText}
              onChange={handleCustomChange}
              rows={2}
              style={{
                width: '100%',
                background: '#2a3942',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                padding: '8px 10px',
                fontSize: '13px',
                resize: 'none',
                outline: 'none',
                boxSizing: 'border-box'
              }}
              placeholder="e.g. Need window cleaning for 200m2 office in Bern..."
            />
          </div>
        </div>

        {/* Right Column: Structured Lead Card with Completeness Score */}
        <div
          style={{
            background: 'rgba(30, 41, 59, 0.7)',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between'
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Extracted Lead Entity
                </span>
                <h4 style={{ margin: '2px 0 0 0', fontSize: '16px', color: '#fff' }}>{activeLead.intentLabel}</h4>
              </div>
              <div
                style={{
                  background: activeLead.completeness >= 85 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                  color: activeLead.completeness >= 85 ? '#34d399' : '#fbbf24',
                  border: activeLead.completeness >= 85 ? '1px solid #10b981' : '1px solid #f59e0b',
                  borderRadius: '20px',
                  padding: '4px 10px',
                  fontSize: '12px',
                  fontWeight: 700
                }}
              >
                {activeLead.completeness}% Complete
              </div>
            </div>

            {/* Progress Bar */}
            <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', marginBottom: '16px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${activeLead.completeness}%`,
                  height: '100%',
                  background: activeLead.completeness >= 85 ? '#10b981' : '#f59e0b',
                  borderRadius: '3px',
                  transition: 'width 0.4s ease'
                }}
              />
            </div>

            {/* Extracted Fields Table */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '4px' }}>
                <span style={{ color: '#94a3b8' }}>Language:</span>
                <span style={{ fontWeight: 600, color: '#cbd5e1' }}>{activeLead.language}</span>
              </div>
              {Object.entries(activeLead.extractedFields).map(([key, val]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '4px' }}>
                  <span style={{ color: '#94a3b8' }}>{key}:</span>
                  <span style={{ fontWeight: 600, color: '#f1f5f9', textAlign: 'right', maxWidth: '60%' }}>{val}</span>
                </div>
              ))}
            </div>

            {/* Missing Fields Notification */}
            {activeLead.missingFields.length > 0 && (
              <div
                style={{
                  background: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid rgba(245, 158, 11, 0.25)',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  fontSize: '12px',
                  color: '#fde68a',
                  marginBottom: '16px'
                }}
              >
                <strong>Pending Info:</strong> {activeLead.missingFields.join(', ')}
              </div>
            )}
          </div>

          {/* Owner 1-Tap Action Guard */}
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '12px',
              marginTop: '10px'
            }}
          >
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px', fontWeight: 600 }}>
              🛡️ Owner in the Loop Action
            </div>
            <div style={{ fontSize: '13px', color: '#e2e8f0', marginBottom: '10px' }}>
              {activeLead.suggestedAction}
            </div>
            <button
              onClick={() => alert(`Simulated Action Executed: "${activeLead.suggestedAction}"`)}
              style={{
                width: '100%',
                background: '#0284c7',
                color: '#fff',
                border: 'none',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
            >
              ✓ 1-Tap Confirm &amp; Dispatch
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
