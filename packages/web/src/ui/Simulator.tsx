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
    id: 'b2b_consulting',
    label: '💼 Professional Services & B2B',
    market: 'trades',
    message:
      'Hello! We are looking for an ongoing compliance & advisory retainer for our 25-person Zurich fintech team starting next month. What are your standard terms and availability for an intro call?',
    lead: {
      intent: 'quote_request',
      intentLabel: 'B2B Advisory Retainer Quote',
      customerName: 'Elena Rossi (Nexus Capital AG)',
      language: 'English (EN)',
      extractedFields: {
        'Service Tier': 'Standard Compliance & Advisory Retainer (15–50 seats)',
        'Client Location': 'Zurich City',
        'Target Start': 'Next Month (12-Month Annual Commitment)',
        'Deliverables': 'Monthly audit reviews, SLA response < 2h, priority access'
      },
      completeness: 95,
      missingFields: [],
      suggestedAction: 'Propose Monthly Retainer (CHF 2\'450 / mo) & Book Intro Call',
      aiResponse:
        'Hello Elena, thank you for reaching out! For a 25-person team, our Standard Advisory Retainer is CHF 2’450.– / month, which includes monthly audit reviews and priority Slack/WhatsApp access. I have reserved slots for an introduction call this Thursday at 10:00 or Friday at 14:00. Would either work for you?'
    }
  },
  {
    id: 'field_services',
    label: '🛠️ Field Services & Trades',
    market: 'trades',
    message:
      'Hi, our central commercial heat pump tripped with error code E04 in central Zurich. Can you dispatch a certified technician for urgent on-site diagnostics today?',
    lead: {
      intent: 'emergency',
      intentLabel: 'Emergency Diagnostic Dispatch',
      customerName: 'Marc Weber (Property Management)',
      language: 'English (EN)',
      extractedFields: {
        'Equipment Type': 'Commercial Heat Pump',
        'Reported Issue': 'Circuit tripped (Fault E04)',
        'Location': 'Zurich Central',
        'SLA Window': 'Same-Day Dispatch (14:00 - 16:00)'
      },
      completeness: 90,
      missingFields: ['Equipment Serial / Access Code'],
      suggestedAction: 'Dispatch Certified Tech Window (Flat Diagnostic Fee: CHF 280.-)',
      aiResponse:
        'Hello Marc, we have flagged this as an urgent priority. Our standard emergency diagnostic fee is CHF 280.–. A certified HVAC technician is available today between 14:00 and 16:00. Would you like to confirm the dispatch?'
    }
  },
  {
    id: 'ecommerce_order',
    label: '🛍️ E-Commerce & Retail (1-Click Pay)',
    market: 'ecommerce',
    message:
      'Bonjour! Je voudrais commander 2 bouteilles de votre Huile d’Olive Bio 500ml et savoir si vous livrez à Genève d’ici vendredi.',
    lead: {
      intent: 'product_enquiry',
      intentLabel: 'Product Order & Instant Checkout',
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
  },
  {
    id: 'clinic_booking',
    label: '🏥 Clinics & Consultations',
    market: 'trades',
    message:
      'Good morning, I would like to book a Comprehensive Preventive Dental Checkup & Hygiene session in Zurich for next Tuesday afternoon if available.',
    lead: {
      intent: 'appointment_request',
      intentLabel: 'Consultation & Hygiene Session',
      customerName: 'Dr. Sarah Jenkins',
      language: 'English (EN)',
      extractedFields: {
        'Treatment': 'Preventive Checkup & Deep Hygiene',
        'Provider': 'Senior Dental Hygienist',
        'Preferred Time': 'Next Tuesday Afternoon (15:30 Available)',
        'Standard Fee': 'CHF 220.00 (Tarif 590 Aligned)'
      },
      completeness: 90,
      missingFields: ['Insurance Policy / ID'],
      suggestedAction: 'Confirm Slot Reservation (Tue 15:30, CHF 220.-)',
      aiResponse:
        'Good morning Sarah! We have an opening for a Comprehensive Dental Checkup & Hygiene next Tuesday at 15:30 with our senior team. The standard rate is CHF 220.–. Shall we lock in this appointment for you?'
    }
  }
];

export function parseCustomMessage(text: string): ExtractedLeadData {
  const isConsulting = /consult|retainer|advisory|legal|audit|agency|b2b/i.test(text);
  const isEmergency = /urgent|notfall|leak|broken|repair|kaputt|heute|today|error|fault/i.test(text);
  const isEcommerce = /order|buy|commander|stock|shipping|livraison|bouteille|price/i.test(text);
  const isFrench = /bonjour|merci|commander|svp/i.test(text);
  const isGerman = /grüezi|guten tag|bitte|wohnung|preis|termin/i.test(text);

  let lang = 'English (EN)';
  if (isGerman) lang = 'German (DE)';
  if (isFrench) lang = 'French (FR)';

  if (isConsulting) {
    return {
      intent: 'quote_request',
      intentLabel: 'Professional Advisory Quote',
      customerName: 'Prospective Client',
      language: lang,
      extractedFields: {
        'Inquiry Type': 'Professional Consultation & Retainer',
        'Summary': text.slice(0, 60),
        'Target Scope': 'Custom Proposal Required'
      },
      completeness: 85,
      missingFields: ['Scope specifications'],
      suggestedAction: 'Draft Custom Service Scope (Standard Rate: CHF 250/h)',
      aiResponse:
        'Thank you for reaching out! Based on your requirements, our standard advisory rate is CHF 250.– / hour. Would you like to schedule an introductory discovery call?'
    };
  }

  if (isEmergency) {
    return {
      intent: 'emergency',
      intentLabel: 'Emergency Service Dispatch',
      customerName: 'Emergency Inbound Caller',
      language: lang,
      extractedFields: {
        'Reported Issue': text.slice(0, 60),
        'Urgency': 'High / Immediate',
        'Dispatch Window': 'Next Available Certified Specialist'
      },
      completeness: 85,
      missingFields: ['Exact address & access info'],
      suggestedAction: 'Dispatch Urgent Specialist (Diagnostic Fee: CHF 280.-)',
      aiResponse:
        'We have prioritized your urgent request. Our standard on-site diagnostic fee is CHF 280.–. A specialist can be dispatched within 2 hours. Would you like to proceed?'
    };
  }

  if (isEcommerce) {
    return {
      intent: 'product_enquiry',
      intentLabel: 'Product Order & Instant Checkout',
      customerName: 'Online Shopper',
      language: lang,
      extractedFields: {
        'Item Request': text.slice(0, 60),
        'Catalog Availability': 'In Stock (Verified)'
      },
      completeness: 90,
      missingFields: ['Shipping Street Address'],
      suggestedAction: 'Draft Stripe 1-Tap Checkout Link',
      aiResponse:
        'Thank you for your order inquiry! The item is in stock. Please click here to complete checkout: https://nuncio.link/pay/chk_demo'
    };
  }

  return {
    intent: 'product_enquiry',
    intentLabel: 'Commercial Product / Service Inquiry',
    customerName: 'Commercial Lead',
    language: lang,
    extractedFields: {
      'Request': text.slice(0, 60),
      'Status': 'Grounded in Catalog Rates'
    },
    completeness: 80,
    missingFields: ['Quantity / Delivery specs'],
    suggestedAction: 'Send Verified Catalog Price & Checkout Link',
    aiResponse:
      'Thank you for your message! We have checked our verified catalog and prepared the quote details for you. How would you like to proceed?'
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
                <span style={{ fontSize: '11px', color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
                  Calculated Trade Quote
                </span>
                <h4 style={{ margin: '2px 0 0 0', fontSize: '17px', fontWeight: 800, color: '#fff' }}>{activeLead.intentLabel}</h4>
              </div>
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.2)',
                  color: '#34d399',
                  border: '1px solid #10b981',
                  borderRadius: '20px',
                  padding: '4px 12px',
                  fontSize: '12px',
                  fontWeight: 700
                }}
              >
                Ready for Approval
              </div>
            </div>

            {/* Field Breakdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '12.5px',
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                  paddingBottom: '4px'
                }}
              >
                <span style={{ color: '#94a3b8' }}>👤 Customer:</span>
                <span style={{ color: '#f8fafc', fontWeight: 500 }}>{activeLead.customerName}</span>
              </div>
              {Object.entries(activeLead.extractedFields).map(([key, val]) => (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '12.5px',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    paddingBottom: '4px'
                  }}
                >
                  <span style={{ color: '#94a3b8' }}>• {key}:</span>
                  <span style={{ color: '#f8fafc', fontWeight: 500, textAlign: 'right' }}>{val}</span>
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
              background: 'rgba(15, 23, 42, 0.95)',
              border: '1px solid #0284c7',
              borderRadius: '10px',
              padding: '14px',
              marginTop: '10px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#38bdf8', fontWeight: 700, marginBottom: '6px' }}>
              <span>📱</span> WhatsApp Alert Sent to Owner's Mobile:
            </div>
            <div style={{ fontSize: '12.5px', color: '#e2e8f0', lineHeight: 1.4, background: '#1e293b', padding: '8px 10px', borderRadius: '6px', fontFamily: 'monospace', marginBottom: '10px' }}>
              🔔 Neue Offerte: {activeLead.customerName}<br />Antworte <b>/approve</b> zum Senden.
            </div>
            <button
              onClick={() => alert(`✅ Quote Approved for ${activeLead.customerName}! Official quote & Stripe payment link sent.`)}
              style={{
                width: '100%',
                background: 'linear-gradient(135deg, #0284c7 0%, #10b981 100%)',
                color: '#fff',
                border: 'none',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'opacity 0.15s ease'
              }}
            >
              ✓ Reply /approve (Send Quote + Payment Link)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
