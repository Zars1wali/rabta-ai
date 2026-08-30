# Legal Compliance & Sole Trader Liability Protection Strategy

**Document Status:** Official Reference & Legal Architecture Guide  
**Entity:** Nuno Miguel Pires Ribeiro (Registered Sole Trader / *Einzelunternehmen* trading as **ZeroPointIntel**, **Nuncio**, and **Rabta AI**)  
**Operating Jurisdiction:** Zurich, Switzerland  
**Applicable Legal Frameworks:** Swiss Code of Obligations (*Obligationenrecht, OR*), Swiss Federal Act on Data Protection (*revDSG*), EU AI Act (Regulation 2024/1689), and EU General Data Protection Regulation (*GDPR*).

---

## 1. Executive Summary

As a Swiss Sole Trader (*Einzelunternehmer*), your personal assets are subject to unlimited liability by default for commercial obligations and operational claims under the Swiss Code of Obligations (*OR Art. 394 et seq.*). When operating an autonomous conversational commerce platform (**Nuncio**) that interacts with end customers on WhatsApp, provides quotes, and processes payments, legal risk must be systematically ring-fenced.

This document formalizes the **5-Layer Legal & Operational Protection Shield** designed to eliminate vendor liability, protect personal assets, and maintain strict compliance with Swiss, European, and Meta Platform policies.

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. CONTRACTUAL SHIELD (Terms of Service, OR Art. 100) │
 ├────────────────────────────────────────────────────────┤
 │ 2. ARCHITECTURAL SHIELD (Non-Binding AI & 1-Tap Owner) │
 ├────────────────────────────────────────────────────────┤
 │ 3. DATA PROCESSOR SHIELD (Swiss revDSG & GDPR DPA)     │
 ├────────────────────────────────────────────────────────┤
 │ 4. PROFESSIONAL INSURANCE (Tech E&O / Cyber Liability) │
 ├────────────────────────────────────────────────────────┤
 │ 5. CORPORATE SHIELD (Upgrade to Swiss GmbH)            │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Layer 1: The Contractual Shield (Terms of Service)

Your B2B SaaS Agreement (*Terms of Service*) is the primary legal boundary between you and the merchant (e.g., `mondar.ch`). Under Swiss law, the following clauses must be incorporated into every merchant contract:

### 2.1 Limitation of Liability (*Haftungsbegrenzung*, OR Art. 100)
* **Liability Cap:** Cumulative total financial liability for any claims arising from the platform is strictly capped at the **total subscription fees paid by the merchant in the preceding three (3) months**, or a fixed maximum of **CHF 500.00** (whichever is lower).
* **Enforceability under Swiss Law (OR Art. 100 Abs. 1):** While liability for intentional unlawful intent (*Absicht*) or gross negligence (*grobe Fahrlässigkeit*) cannot be excluded, liability for **slight negligence (*leichte Fahrlässigkeit*) and auxiliary persons (*Hilfspersonen*, OR Art. 101)** is 100% excludable and legally binding.

### 2.2 Exclusion of Consequential Damages (*Ausschluss von Folgeschäden*)
* You expressly exclude all liability for:
  1. Lost profits (*entgangener Gewinn*), business interruption, or loss of goodwill.
  2. Loss, corruption, or delays of customer inquiries.
  3. Third-party upstream outages (Meta Cloud API, Deepgram, Gemini/Mistral, or Stripe).

### 2.3 Mandatory Merchant Indemnification (*Freistellungsklausel*)
* The merchant explicitly agrees to **indemnify, defend, and hold harmless** Nuno Miguel Pires Ribeiro / ZeroPointIntel against any third-party lawsuits, customer claims, administrative fines, or legal expenses resulting from:
  1. Faulty product delivery, broken items, or defective trade execution performed by the merchant.
  2. Inaccurate pricing, inventory discrepancies, or service descriptions supplied by the merchant's catalog.
  3. Sending messages or marketing communications without valid customer opt-in consent.

---

## 3. Layer 2: Architectural Shield (The "Human-in-the-Loop")

The technical architecture of Nuncio provides structural legal immunity:

### 3.1 Non-Binding AI Estimations (*Invitatio ad offerendum*)
* Legally, autonomous AI messages sent to customers are classified as *preliminary informational estimates* (*invitatio ad offerendum* / Aufforderung zur Offertstellung), not binding contractual offers.
* The system prompt includes explicit guardrails that prices quoted in chat are subject to final merchant confirmation and site inspection where applicable.

### 3.2 The 1-Tap `/approve` Control Plane
* Money-moving actions (issuing a binding commercial quote, scheduling a guaranteed service slot, or executing refunds) require the merchant owner's explicit confirmation via the WhatsApp `/approve` command or web dashboard.
* **Legal Result:** The business owner is the sole legal author and signatory of the transaction. The software provider is strictly a communications carrier.

### 3.3 Disclaimer of Agency (*Keine Stellvertretung*)
* The terms make clear that Nuncio does not act as an authorized commercial agent (*Handlungsbevollmächtigter* or *Stellvertreter*) with power of attorney to bind the merchant.

---

## 4. Layer 3: Data Protection & Regulatory Shield

### 4.1 Data Controller vs. Data Processor Separation
* **Merchant = Data Controller (*Verantwortlicher*):** The merchant is legally responsible for customer personal data, phone number collection, and lawful basis under the Swiss Data Protection Act (*revDSG Art. 5*) and EU GDPR (*Art. 4(7)*).
* **ZeroPointIntel = Data Processor (*Auftragsbearbeiter*):** You only process customer messages on the documented instructions of the merchant under a standardized Data Processing Agreement (*DPA*).

### 4.2 EU AI Act Article 50 Transparency
* Nuncio automatically identifies itself as an artificial intelligence assistant on the first inbound customer message (*"Grüezi! Ich bin der digitale Assistent von..."*), fulfilling the mandatory transparency obligations of EU AI Act Article 50 and Swiss consumer fair trade guidelines.

### 4.3 Data Retention & Tenant RLS Isolation
* Customer transcripts are protected by PostgreSQL Row-Level Security (*RLS*) with strict tenant isolation.
* Standard data retention is set to 30–90 days with automated 1-click customer data deletion endpoints.

---

## 5. Layer 4: Professional Insurance Blueprint

To eliminate personal financial exposure against unexpected legal defense costs:

| Insurance Policy | Swiss Term | What It Covers | Recommended Providers |
| :--- | :--- | :--- | :--- |
| **Professional Indemnity (Tech E&O)** | *Vermögensschaden-haftpflichtversicherung* | Software errors, platform bugs, integration failures, and client financial loss claims. | Helvetia, Mobiliar, Hiscox, AXA |
| **General Commercial Liability** | *Betriebshaftpflicht-versicherung* | General operational liabilities and third-party property damage. | Die Mobiliar, Zurich Insurance |
| **Cyber Risk & Data Breach** | *Cyber-Versicherung* | Forensic investigation, legal defense, and notification costs in case of a security incident. | Helvetia, AXA, Hiscox |

*Estimated annual premium for a Swiss sole trader:* ~CHF 600 – CHF 1'200 / year.

---

## 6. Layer 5: Corporate Structuring & GmbH Migration Roadmap

As revenue and client volume scale, transitioning from a sole proprietorship to a corporate entity is the definitive step to remove personal liability:

### 6.1 Formation of a Swiss GmbH (*Gesellschaft mit beschränkter Haftung*)
* **Minimum Share Capital (*Stammkapital*):** CHF 20,000 (can be paid in cash or via a contribution in kind / *Sacheinlage* of software IP).
* **Liability Firewall:** The company (*juristische Person*) is solely liable with its company assets. The owner's private savings, real estate, and personal bank accounts are completely shielded by the corporate veil.
* **Commercial Register (*Handelsregister*):** Public listing in the Canton of Zurich commercial register.

### 6.2 Recommended Trigger Points for GmbH Formation:
1. Reaching **3–5 active paying B2B clients** or > CHF 3'000 MRR.
2. Handling high-ticket commercial transactions (> CHF 10'000 per quote).
3. Hiring contractors, employees, or taking external investment.

---

## 7. Practical Merchant Onboarding Safety Checklist

Before activating any live customer (e.g. `mondar.ch`):

- [ ] **1. Terms Acceptance:** Ensure the merchant accepts the [Terms of Service](./TERMS_OF_SERVICE.md) containing the liability limitation and indemnity clauses.
- [ ] **2. DPA Execution:** Ensure the merchant executes the [Data Processing Agreement](./DATA_PROCESSING_AGREEMENT.md).
- [ ] **3. Verified Catalog:** Review the merchant's catalog file to ensure all prices, room rates, and warranties match their verified pricing.
- [ ] **4. Owner WhatsApp Number Verification:** Confirm the merchant's owner mobile number is registered in `TenantConfig.channels` for `/approve` notifications.
- [ ] **5. AI Disclosure Active:** Verify that the automated greeting includes the AI identity disclaimer in compliance with EU AI Act Art. 50.

---

## 8. Summary of Legal Documentation in Repo

* **Terms of Service:** [`legal/TERMS_OF_SERVICE.md`](./TERMS_OF_SERVICE.md)
* **Privacy Policy:** [`legal/PRIVACY_POLICY.md`](./PRIVACY_POLICY.md)
* **Data Processing Agreement (DPA):** [`legal/DATA_PROCESSING_AGREEMENT.md`](./DATA_PROCESSING_AGREEMENT.md)
* **Technical Compliance Center:** Hosted at `https://zeropointintel.com/privacy` and `https://zeropointintel.com/terms`
