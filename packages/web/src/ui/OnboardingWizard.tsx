import React, { useState } from 'react';
import type { CatalogItem, VerifyResult } from '@salesops/types';

export interface OnboardingWizardProps {
  apiBaseUrl?: string;
  onCompleted?: (result: { tenantId: string; embedSnippet: string }) => void;
}

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({
  apiBaseUrl = '',
  onCompleted
}) => {
  const [step, setStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [slug, setSlug] = useState<string>('minha-loja');
  const [displayName, setDisplayName] = useState<string>('Minha Loja Online');
  const [sourceKind, setSourceKind] = useState<'csv' | 'woocommerce' | 'json'>('csv');
  const [csvData, setCsvData] = useState<string>(
    'SKU,Name,Price,Category,Description\nPROD-01,"Camisa Algodão",29.90,Vestuário,"Camisa 100% algodão"\nPROD-02,"Calças Jeans",59.00,Vestuário,"Calças confortáveis"'
  );
  const [wooUrl, setWooUrl] = useState<string>('https://minhaloja.pt');
  const [wooKey, setWooKey] = useState<string>('');
  const [wooSecret, setWooSecret] = useState<string>('');

  // Verification results
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);

  // Policies
  const [shippingPolicy, setShippingPolicy] = useState<string>('Envios para Portugal Continental em 24-48h (Grátis acima de 50€).');
  const [returnPolicy, setReturnPolicy] = useState<string>('30 dias para devoluções gratuitas com etiqueta pré-paga.');
  const [warrantyPolicy, setWarrantyPolicy] = useState<string>('Garantia legal de 3 anos para todos os artigos de consumo.');
  const [paymentPolicy, setPaymentPolicy] = useState<string>('MB WAY, Multibanco, Cartão de Crédito e Klarna.');

  // Persona & Closes
  const [personaTone, setPersonaTone] = useState<'warm_direct' | 'professional_technical' | 'casual_enthusiastic'>('warm_direct');
  const [greeting, setGreeting] = useState<string>('Olá! Como posso ajudar na sua compra hoje?');
  const [closeAction, setCloseAction] = useState<'preview' | 'lead' | 'quote'>('lead');

  // Completed Provisioning
  const [provisioned, setProvisioned] = useState<{ tenantId: string; embedSnippet: string } | null>(null);

  const handleVerifySource = async () => {
    setLoading(true);
    setError(null);

    const sourceConfig =
      sourceKind === 'csv'
        ? { csvData, defaultCurrency: 'EUR' }
        : sourceKind === 'woocommerce'
        ? { baseUrl: wooUrl, consumerKey: wooKey, consumerSecret: wooSecret, defaultCurrency: 'EUR' }
        : { jsonData: '[]' };

    try {
      const res = await fetch(`${apiBaseUrl}/api/salesops/onboarding/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourceKind, sourceConfig })
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Falha na verificação da fonte de catálogo');
      } else {
        setVerifyResult(data);
        setStep(2);
      }
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleProvisionTenant = async () => {
    setLoading(true);
    setError(null);

    const sourceConfig =
      sourceKind === 'csv'
        ? { csvData, defaultCurrency: 'EUR' }
        : sourceKind === 'woocommerce'
        ? { baseUrl: wooUrl, consumerKey: wooKey, consumerSecret: wooSecret, defaultCurrency: 'EUR' }
        : { jsonData: '[]' };

    const draft = {
      slug,
      displayName,
      tier: 'standard' as const,
      locales: ['pt-PT', 'en'],
      currency: 'EUR' as const,
      sourceKind,
      sourceConfig,
      policy: {
        shipping: shippingPolicy,
        returns: returnPolicy,
        warranty: warrantyPolicy,
        payments: paymentPolicy
      },
      closes: [{ kind: closeAction }],
      persona: {
        tone: personaTone,
        greeting,
        escalationPhrase: 'Vou encaminhar este contacto para a nossa equipa de apoio.'
      },
      allowedOrigins: ['*']
    };

    try {
      const res = await fetch(`${apiBaseUrl}/api/salesops/onboarding/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft)
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Erro ao criar e provisionar assistente');
      } else {
        setProvisioned({ tenantId: data.tenantId, embedSnippet: data.embedSnippet });
        setStep(5);
        if (onCompleted) {
          onCompleted({ tenantId: data.tenantId, embedSnippet: data.embedSnippet });
        }
      }
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif', padding: '24px' }}>
      <header style={{ marginBottom: '24px', borderBottom: '1px solid #e5e7eb', paddingBottom: '16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#111827', margin: '0 0 8px 0' }}>
          Assistente de Vendas SalesOps — Configuração Rápida
        </h1>
        <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>
          Passo {step} de 5: {step === 1 ? 'Conectar Catálogo' : step === 2 ? 'Amostragem & Diagnóstico' : step === 3 ? 'Políticas da Loja' : step === 4 ? 'Personalidade & Fecho' : 'Código de Integração'}
        </p>
      </header>

      {error && (
        <div style={{ backgroundColor: '#fee2e2', border: '1px solid #ef4444', color: '#b91c1c', padding: '12px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px' }}>
          {error}
        </div>
      )}

      {/* Step 1: Connect Source */}
      {step === 1 && (
        <div>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>Nome da Loja</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>Identificador Único (Slug)</label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>Fonte de Produtos</label>
            <select
              value={sourceKind}
              onChange={(e) => setSourceKind(e.target.value as 'csv' | 'woocommerce' | 'json')}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
            >
              <option value="csv">Ficheiro CSV / Folha de Cálculo</option>
              <option value="woocommerce">Loja WooCommerce (API REST v3)</option>
            </select>
          </div>

          {sourceKind === 'csv' && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>Dados CSV (Cabeçalho + Linhas)</label>
              <textarea
                rows={5}
                value={csvData}
                onChange={(e) => setCsvData(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px', fontFamily: 'monospace', fontSize: '12px' }}
              />
            </div>
          )}

          {sourceKind === 'woocommerce' && (
            <div>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>URL da Loja</label>
                <input
                  type="url"
                  value={wooUrl}
                  onChange={(e) => setWooUrl(e.target.value)}
                  placeholder="https://minhaloja.pt"
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                />
              </div>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>Consumer Key</label>
                <input
                  type="text"
                  value={wooKey}
                  onChange={(e) => setWooKey(e.target.value)}
                  placeholder="ck_..."
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                />
              </div>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>Consumer Secret</label>
                <input
                  type="password"
                  value={wooSecret}
                  onChange={(e) => setWooSecret(e.target.value)}
                  placeholder="cs_..."
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                />
              </div>
            </div>
          )}

          <button
            onClick={handleVerifySource}
            disabled={loading}
            style={{ padding: '10px 20px', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            {loading ? 'A verificar produtos...' : 'Verificar e Continuar →'}
          </button>
        </div>
      )}

      {/* Step 2: Verification Results */}
      {step === 2 && verifyResult && (
        <div>
          <div style={{ backgroundColor: '#ecfdf5', border: '1px solid #10b981', color: '#065f46', padding: '12px', borderRadius: '6px', marginBottom: '16px' }}>
            ✓ Conexão estabelecida com sucesso! <strong>{verifyResult.itemCount} produtos</strong> encontrados no catálogo.
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '12px' }}>Amostra de 5 Produtos Verificados</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f3f4f6', textAlign: 'left' }}>
                <th style={{ padding: '8px', border: '1px solid #e5e7eb' }}>SKU</th>
                <th style={{ padding: '8px', border: '1px solid #e5e7eb' }}>Nome</th>
                <th style={{ padding: '8px', border: '1px solid #e5e7eb' }}>Preço</th>
                <th style={{ padding: '8px', border: '1px solid #e5e7eb' }}>Disponível</th>
              </tr>
            </thead>
            <tbody>
              {verifyResult.sample.map((item: CatalogItem) => (
                <tr key={item.sku}>
                  <td style={{ padding: '8px', border: '1px solid #e5e7eb', fontFamily: 'monospace' }}>{item.sku}</td>
                  <td style={{ padding: '8px', border: '1px solid #e5e7eb' }}>{item.name}</td>
                  <td style={{ padding: '8px', border: '1px solid #e5e7eb' }}>{(item.priceMinor / 100).toFixed(2)} {item.currency}</td>
                  <td style={{ padding: '8px', border: '1px solid #e5e7eb' }}>{item.available ? '✓ Sim' : '✗ Esgotado'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => setStep(1)} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer' }}>← Voltar</button>
            <button onClick={() => setStep(3)} style={{ padding: '8px 20px', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>Políticas da Loja →</button>
          </div>
        </div>
      )}

      {/* Step 3: Store Policies Form */}
      {step === 3 && (
        <div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Envios & Prazos</label>
            <textarea rows={2} value={shippingPolicy} onChange={(e) => setShippingPolicy(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }} />
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Trocas & Devoluções</label>
            <textarea rows={2} value={returnPolicy} onChange={(e) => setReturnPolicy(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }} />
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Garantia</label>
            <textarea rows={2} value={warrantyPolicy} onChange={(e) => setWarrantyPolicy(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }} />
          </div>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Métodos de Pagamento</label>
            <input type="text" value={paymentPolicy} onChange={(e) => setPaymentPolicy(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }} />
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => setStep(2)} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer' }}>← Voltar</button>
            <button onClick={() => setStep(4)} style={{ padding: '8px 20px', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>Personalidade →</button>
          </div>
        </div>
      )}

      {/* Step 4: Persona & Close */}
      {step === 4 && (
        <div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Tom de Comunicação</label>
            <select value={personaTone} onChange={(e) => setPersonaTone(e.target.value as 'warm_direct' | 'professional_technical' | 'casual_enthusiastic')} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}>
              <option value="warm_direct">Caloroso & Direto (Recomendado)</option>
              <option value="professional_technical">Profissional & Técnico</option>
              <option value="casual_enthusiastic">Descontraído & Entusiasta</option>
            </select>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Mensagem Inicial (Saudação)</label>
            <input type="text" value={greeting} onChange={(e) => setGreeting(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }} />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>Ação Principal de Fecho</label>
            <select value={closeAction} onChange={(e) => setCloseAction(e.target.value as 'preview' | 'lead' | 'quote')} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}>
              <option value="lead">Recolha de Lead Qualificada (Nome, Email, Telefone)</option>
              <option value="quote">Orçamento / Cotação Formal Imediata</option>
              <option value="preview">Demonstração Personalizada (€50)</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => setStep(3)} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer' }}>← Voltar</button>
            <button onClick={handleProvisionTenant} disabled={loading} style={{ padding: '10px 24px', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>
              {loading ? 'A criar assistente...' : '🚀 Ativar Assistente de Vendas'}
            </button>
          </div>
        </div>
      )}

      {/* Step 5: Completed & Embed Code */}
      {step === 5 && provisioned && (
        <div>
          <div style={{ backgroundColor: '#ecfdf5', border: '1px solid #10b981', color: '#065f46', padding: '16px', borderRadius: '6px', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 'bold', margin: '0 0 8px 0' }}>🎉 Assistente Ativo e Pronto a Vender!</h2>
            <p style={{ margin: 0, fontSize: '14px' }}>
              O assistente para a loja <strong>{displayName}</strong> foi configurado com sucesso e o catálogo de produtos sincronizado.
            </p>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 'bold', marginBottom: '6px' }}>Código de Integração (Cole antes de &lt;/body&gt; na sua loja)</label>
            <div style={{ position: 'relative' }}>
              <textarea
                readOnly
                rows={3}
                value={provisioned.embedSnippet}
                style={{ width: '100%', padding: '10px', backgroundColor: '#1f2937', color: '#10b981', border: 'none', borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px' }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
