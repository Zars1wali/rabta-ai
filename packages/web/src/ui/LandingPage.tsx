import React, { useState } from 'react';
import { Simulator } from './Simulator.js';

export interface LandingPageProps {
  onGetStarted?: () => void;
  onBookDemo?: () => void;
  brandName?: string;
}

export function LandingPage({
  onGetStarted,
  onBookDemo,
  brandName = 'Nuncio by ZeroPointIntel'
}: LandingPageProps): React.ReactElement {
  const [activeMarketTab, setActiveMarketTab] = useState<'trades' | 'ecommerce'>('trades');

  return (
    <div
      style={{
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"',
        color: '#0f172a',
        backgroundColor: '#090d16',
        colorScheme: 'dark',
        minHeight: '100vh',
        lineHeight: 1.6
      }}
    >
      {/* 1. Header Navigation */}
      <header
        style={{
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          position: 'sticky',
          top: 0,
          backgroundColor: 'rgba(9, 13, 22, 0.85)',
          backdropFilter: 'blur(12px)',
          zIndex: 50
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '16px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          {/* Logo & Brand */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img
              src="/logo.svg"
              alt="Nuncio Logo"
              width="36"
              height="36"
              style={{ display: 'block', borderRadius: '6px' }}
            />
            <div>
              <span style={{ fontSize: '18px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                {brandName.includes('by') ? brandName.split('by')[0]?.trim() : brandName}
              </span>
              {brandName.includes('by') && (
                <span
                  style={{
                    fontSize: '11px',
                    color: '#94a3b8',
                    marginLeft: '8px',
                    background: 'rgba(255,255,255,0.06)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}
                >
                  by {brandName.split('by')[1]?.trim()}
                </span>
              )}
            </div>
          </div>

          {/* Nav Links & CTA */}
          <nav style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <a
              href="#solutions"
              style={{ color: '#cbd5e1', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}
            >
              Solutions
            </a>
            <a
              href="#simulator"
              style={{ color: '#cbd5e1', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}
            >
              Live Demo
            </a>
            <a
              href="#compliance"
              style={{ color: '#cbd5e1', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}
            >
              Compliance &amp; Trust
            </a>
            <a
              href="#portfolio"
              style={{ color: '#cbd5e1', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}
            >
              Portfolio
            </a>
            <button
              onClick={onGetStarted}
              style={{
                background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                color: '#ffffff',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 14px rgba(16, 185, 129, 0.35)',
                transition: 'transform 0.15s ease'
              }}
            >
              Start Free Trial
            </button>
          </nav>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section style={{ padding: '72px 24px 48px 24px', maxWidth: '1200px', margin: '0 auto', textAlign: 'center' }}>
        {/* Meta Tech Provider Tag */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
          <span
            style={{
              background: 'rgba(6, 182, 212, 0.12)',
              color: '#38bdf8',
              border: '1px solid rgba(6, 182, 212, 0.3)',
              borderRadius: '24px',
              padding: '6px 14px',
              fontSize: '12.5px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#38bdf8' }} />
            Official Meta Tech Provider • WhatsApp Cloud API
          </span>
        </div>

        {/* Hero Title */}
        <h1
          style={{
            fontSize: 'clamp(32px, 5vw, 54px)',
            fontWeight: 800,
            color: '#f8fafc',
            lineHeight: 1.15,
            letterSpacing: '-0.03em',
            maxWidth: '960px',
            margin: '0 auto 20px auto'
          }}
        >
          Every WhatsApp enquiry answered in under a minute —{' '}
          <span
            style={{
              background: 'linear-gradient(135deg, #34d399 0%, #38bdf8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            turned into a structured lead
          </span>{' '}
          for your business.
        </h1>

        {/* Hero Subhead */}
        <p
          style={{
            fontSize: '18px',
            color: '#94a3b8',
            maxWidth: '780px',
            margin: '0 auto 36px auto',
            lineHeight: 1.6
          }}
        >
          Never lose a high-value customer while you are on a ladder, in a meeting, or on-site. Nuncio autonomously
          qualifies trade inquiries, transcribes Swiss German voice notes, and drafts verified quotes with zero price
          hallucination.
        </p>

        {/* Hero CTAs */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap', marginBottom: '48px' }}>
          <button
            onClick={onGetStarted}
            style={{
              background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
              color: '#ffffff',
              border: 'none',
              padding: '14px 28px',
              borderRadius: '10px',
              fontSize: '16px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 8px 20px rgba(16, 185, 129, 0.3)'
            }}
          >
            Connect Your WhatsApp Number
          </button>
          <button
            onClick={onBookDemo}
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              color: '#f1f5f9',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              padding: '14px 28px',
              borderRadius: '10px',
              fontSize: '16px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Schedule Live Demo
          </button>
        </div>

        {/* Interactive Simulator Section */}
        <div id="simulator" style={{ marginTop: '24px', textAlign: 'left' }}>
          <Simulator />
        </div>
      </section>

      {/* 3. Dual Market Solutions */}
      <section id="solutions" style={{ padding: '80px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
            Built for Businesses Where Response Speed Wins Deals
          </h2>
          <p style={{ fontSize: '16px', color: '#94a3b8', maxWidth: '640px', margin: '12px auto 0 auto' }}>
            Choose your business model to see how Nuncio accelerates revenue capture.
          </p>

          {/* Market Tab Switcher */}
          <div
            style={{
              display: 'inline-flex',
              background: 'rgba(255,255,255,0.06)',
              padding: '4px',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.1)',
              marginTop: '24px'
            }}
          >
            <button
              onClick={() => setActiveMarketTab('trades')}
              style={{
                background: activeMarketTab === 'trades' ? '#059669' : 'transparent',
                color: '#fff',
                border: 'none',
                padding: '8px 20px',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              🛠️ Service Trades &amp; Local Pros
            </button>
            <button
              onClick={() => setActiveMarketTab('ecommerce')}
              style={{
                background: activeMarketTab === 'ecommerce' ? '#059669' : 'transparent',
                color: '#fff',
                border: 'none',
                padding: '8px 20px',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              🛍️ E-Commerce &amp; Retail Stores
            </button>
          </div>
        </div>

        {/* Tab 1: Service Trades */}
        {activeMarketTab === 'trades' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>📐</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Automated Quote Extraction
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                Extracts square meters (m²), number of rooms, property type, postal code, and target dates into an
                actionable lead record before you even pick up your phone.
              </p>
            </div>

            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>🎙️</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Swiss German Voice Notes
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                Customers send voice notes in Swiss German (Mundart). Nuncio transcribes, normalizes to clean business
                German, and answers with polished professionalism.
              </p>
            </div>

            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>🛡️</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Owner-in-the-Loop Safeguards
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                No artificial price discounts or hallucinations. The AI prepares the proposal based on your verified rate
                card; you tap one button to approve and book.
              </p>
            </div>
          </div>
        )}

        {/* Tab 2: E-Commerce */}
        {activeMarketTab === 'ecommerce' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>📦</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Real-Time Stock &amp; Catalog Sync
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                Syncs with Shopify and WooCommerce to confirm real-time inventory and delivery estimates directly inside
                the WhatsApp chat stream.
              </p>
            </div>

            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>💳</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Instant Stripe Checkout Links
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                Drafts exact orders and sends secure 1-click Stripe payment links so shoppers can complete their purchase
                instantly without leaving WhatsApp.
              </p>
            </div>

            <div
              style={{
                background: '#111827',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '14px',
                padding: '28px'
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '14px' }}>🌍</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 10px 0' }}>
                Multilingual Conversions
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', margin: 0 }}>
                Seamlessly negotiates and supports customers in French, German, Italian, and English with consistent
                catalog price grounding.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* 4. Compliance & Swiss Trust Center */}
      <section
        id="compliance"
        style={{
          background: '#0d131f',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          padding: '80px 24px'
        }}
      >
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '48px' }}>
            <span
              style={{
                color: '#34d399',
                fontSize: '12px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em'
              }}
            >
              Swiss &amp; European Trust Center
            </span>
            <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#f8fafc', margin: '8px 0' }}>
              Compliant by Design. Zero Data Compromises.
            </h2>
            <p style={{ fontSize: '16px', color: '#94a3b8', maxWidth: '640px', margin: '0 auto' }}>
              Built to meet the highest regulatory standards across Switzerland and the European Union.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
            <div
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                padding: '24px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '16px', marginBottom: '8px' }}>
                Meta Tech Provider
              </div>
              <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
                Direct official integration via Meta Cloud API with merchant-controlled phone numbers and Embedded
                Signup.
              </p>
            </div>

            <div
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                padding: '24px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#34d399', fontSize: '16px', marginBottom: '8px' }}>
                EU AI Act Article 50
              </div>
              <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
                Full transparent disclosure informing users that they are interacting with an AI assistant.
              </p>
            </div>

            <div
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                padding: '24px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#a78bfa', fontSize: '16px', marginBottom: '8px' }}>
                Swiss revDSG &amp; GDPR
              </div>
              <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
                Strict European data residency, tenant Row-Level Security (RLS) isolation, and 1-click user data
                deletion.
              </p>
            </div>

            <div
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                padding: '24px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#fbbf24', fontSize: '16px', marginBottom: '8px' }}>
                Zero Price Invention
              </div>
              <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
                Deterministic catalog verification ensuring AI never promises unverified discounts or out-of-stock items.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Deep-Tech Portfolio & Engineering Pedigree */}
      <section id="portfolio" style={{ padding: '80px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <span
            style={{
              color: '#94a3b8',
              fontSize: '12px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em'
            }}
          >
            ZeroPointIntel Engineering
          </span>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#f8fafc', margin: '8px 0' }}>
            High-Assurance Distributed Systems Pedigree
          </h2>
          <p style={{ fontSize: '16px', color: '#94a3b8', maxWidth: '640px', margin: '0 auto' }}>
            Nuncio is engineered on ZeroPointIntel's high-reliability distributed architecture and cybersecurity
            foundations.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          <div
            style={{
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '12px',
              padding: '24px'
            }}
          >
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: '#f8fafc', margin: '0 0 8px 0' }}>
              Telemetry &amp; Edge Ingress
            </h3>
            <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
              High-throughput message pipeline capable of signature verification, deduplication, and routing with sub-100ms
              latency.
            </p>
          </div>

          <div
            style={{
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '12px',
              padding: '24px'
            }}
          >
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: '#f8fafc', margin: '0 0 8px 0' }}>
              Multi-Tenant Security &amp; RLS
            </h3>
            <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
              Hardware and database-enforced Row-Level Security isolating customer data across PostgreSQL storage layers.
            </p>
          </div>

          <div
            style={{
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '12px',
              padding: '24px'
            }}
          >
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: '#f8fafc', margin: '0 0 8px 0' }}>
              Autonomous Conversational Commerce
            </h3>
            <p style={{ fontSize: '13.5px', color: '#94a3b8', margin: 0 }}>
              Multi-model LLM routing (Gemini 2.5 + Mistral EU) with fallback safety layers and owner approval workflows.
            </p>
          </div>
        </div>
      </section>

      {/* 6. Footer */}
      <footer
        style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          backgroundColor: '#070a10',
          padding: '48px 24px 32px 24px'
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '20px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img src="/logo.svg" alt="Nuncio" width="28" height="28" style={{ borderRadius: '4px' }} />
            <span style={{ fontSize: '14px', color: '#94a3b8' }}>
              © 2026 <strong>ZeroPointIntel</strong> (Nuno Miguel Pires Ribeiro). All rights reserved.
            </span>
          </div>

          <div style={{ display: 'flex', gap: '24px', fontSize: '13px' }}>
            <a href="/privacy" style={{ color: '#94a3b8', textDecoration: 'none' }}>
              Privacy Policy
            </a>
            <a href="/terms" style={{ color: '#94a3b8', textDecoration: 'none' }}>
              Terms of Service
            </a>
            <a href="/dpa" style={{ color: '#94a3b8', textDecoration: 'none' }}>
              Data Processing Agreement
            </a>
            <a href="/privacy#user-data-deletion" style={{ color: '#94a3b8', textDecoration: 'none' }}>
              Data Deletion
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
