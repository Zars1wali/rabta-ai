# Privacy Policy

**Effective Date:** August 30, 2026  
**Last Updated:** August 30, 2026  

---

## 1. Data Controller & Operator Identity

This application and service (**Zero Point Intel**, **Nuncio**, **Rabta AI**) is operated by:

* **Operator / Data Controller:** Nuno Miguel Pires Ribeiro (Registered Sole Trader / *Einzelunternehmen* trading as **Zero Point Intel**)
* **Registered Address:** Mina-Hess-Strasse 6, CH-8953 Dietikon, Switzerland
* **Contact Email:** `info@zeropointintel.com` / `privacy@zeropointintel.com`
* **Website:** [https://zeropointintel.com](https://zeropointintel.com)
* **Jurisdiction & Compliance:** Swiss Federal Act on Data Protection (revDSG / FADP) and European Union General Data Protection Regulation (GDPR - Regulation (EU) 2016/679).

---

## 2. Scope & Roles

* **When you visit our website or subscribe to our SaaS platform:** We act as the **Data Controller** for your account, billing, and direct communication data.
* **When businesses ("Merchants" / "Tenants") use Nuncio to manage customer WhatsApp conversations:** The Merchant is the **Data Controller**, and Nuncio acts as a **Data Processor** under Art. 28 GDPR. Our Data Processing Agreement (DPA) governs this processing.

---

## 3. Data We Collect and Process

### A. Account & Billing Information (Platform Users / Merchants)
* Full name, business trade name, and email address.
* Billing details, tax identification (NIF/VAT), and payment status (processed securely via Stripe; we do not store full credit card numbers).
* Authentication records, login timestamps, and session tokens.

### B. WhatsApp Conversation & Customer Data (Processor Role)
* WhatsApp User ID (`wa_id`), phone number in E.164 format, and profile name.
* Inbound and outbound message text, interactive button selections, and timestamps.
* Audio voice notes (temporarily stored for speech-to-text transcription).
* Lead and quote request fields (e.g., service location, requested dimensions, service frequency, quote value).

### C. Technical & Infrastructure Telemetry
* IP addresses, browser user-agent, API request logs, and webhook delivery signatures.

---

## 4. Purposes and Legal Bases for Processing

Under GDPR Article 6, we process personal data based on the following legal grounds:

1. **Performance of a Contract (Art. 6(1)(b) GDPR):** Providing the Nuncio AI conversational assistant, delivering trade quote captures, processing subscriptions, and executing owner commands.
2. **Compliance with Legal Obligations (Art. 6(1)(c) GDPR):** Complying with accounting, tax, and invoicing regulations.
3. **Legitimate Interests (Art. 6(1)(f) GDPR):** Preventing abuse, detecting fraudulent traffic, securing webhook ingress, and maintaining multi-tenant database isolation.
4. **Consent (Art. 6(1)(a) GDPR):** Where opt-in consent is explicitly given by the user for marketing communications or optional features.

---

## 5. Third-Party Sub-Processors & Data Residency

We exclusively partner with enterprise infrastructure and AI providers adhering to strict European and Swiss data protection standards:

| Sub-Processor | Purpose | Location / Data Residency | Privacy Framework |
| :--- | :--- | :--- | :--- |
| **Meta Platforms Ireland Ltd.** | WhatsApp Cloud API & Embedded Signup | European Union (Ireland) | GDPR DPA / Meta Tech Provider Terms |
| **Stripe Payments Europe, Ltd.** | Payment Processing & Billing Subscriptions | European Union (Ireland) | PCI-DSS Level 1 / GDPR Compliant |
| **Google Cloud / Vertex AI** | AI Model Inference (Gemini 2.5 / 3.x) | European Union (Frankfurt / Belgium) | ISO 27001 / EU Model Clauses |
| **Mistral AI SAS** | EU-Residency AI Model Inference | European Union (Paris, France) | EU-Native / GDPR Compliant |
| **Deepgram, Inc.** | Voice Note Audio Transcription | European Union / USA (SOC 2 Type II) | Standard Contractual Clauses |
| **Neon / Supabase (PostgreSQL)** | Multi-Tenant Database Storage with RLS | European Union (Frankfurt, Germany) | Encrypted at Rest & in Transit |

---

## 6. Data Retention & Deletion Policy

* **WhatsApp Message Data:** Retained for the default tenant retention window (default 24 months, tenant-configurable) to allow CRM history and lead management.
* **Transient Audio Files:** Voice notes sent via WhatsApp are transcribed immediately. Audio binaries are purged within 30 days of processing.
* **Account Deletion:** When an account or contact is deleted, all associated message rows, transcripts, and embeddings are permanently purged within 30 days.

---

## 7. Data Subject Rights (GDPR & revDSG)

Under European and Swiss privacy laws, data subjects hold the following rights:

1. **Right of Access (Art. 15 GDPR):** Request a copy of the personal data held about you.
2. **Right to Rectification (Art. 16 GDPR):** Correct inaccurate or incomplete personal records.
3. **Right to Erasure / "Right to be Forgotten" (Art. 17 GDPR):** Request permanent deletion of your data.
4. **Right to Restriction of Processing (Art. 18 GDPR):** Request limitation of data processing.
5. **Right to Data Portability (Art. 20 GDPR):** Receive data in a structured, commonly used, machine-readable JSON format.
6. **Right to Object (Art. 21 GDPR):** Object to processing based on legitimate interests.

---

## 8. User Data Deletion Request Instructions

In compliance with Meta Platform Policies and GDPR, users may request deletion of their data at any time:

1. **Email Request:** Send an email to `ops@zeropointintel.com` or `privacy@zeropointintel.com` with the subject line *"Data Deletion Request"*, specifying your WhatsApp phone number or registered email.
2. **Automated Callback / Endpoint:** Data deletion requests submitted via Meta Platform User Data Deletion callbacks are processed automatically by our deletion service within 48 hours, and a confirmation tracking code is returned.

---

## 9. Contact Information
 
For any privacy-related inquiries or to exercise your statutory rights:
 
* **Data Protection Officer / Controller:** Nuno Miguel Pires Ribeiro
* **Address:** Mina-Hess-Strasse 6, CH-8953 Dietikon, Switzerland
* **Email:** `info@zeropointintel.com` / `privacy@zeropointintel.com`
