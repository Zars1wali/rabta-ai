# Data Processing Agreement (DPA)

**Effective Date:** August 30, 2026  
**Pursuant to:** Article 28 of Regulation (EU) 2016/679 (General Data Protection Regulation - GDPR) and the Swiss Federal Act on Data Protection (revDSG / FADP).

---

## 1. Parties and Scope

This Data Processing Agreement ("DPA") is entered into by and between:
* **The Customer / Merchant / Tenant:** The entity or individual using the Nuncio software platform ("Data Controller").
* **The Service Provider:** **Nuno Miguel Pires Ribeiro** (Freelancer / Sole Trader trading as **ZeroPointIntel** / **Nuncio** / **Rabta AI**, "Data Processor").

This DPA applies to the processing of personal data by the Data Processor on behalf of the Data Controller in connection with the provision of the Nuncio conversational automation service.

---

## 2. Subject Matter, Nature, and Purpose of Processing

* **Subject Matter:** Automated ingestion, routing, transcription, AI grounding, and delivery of customer communications via the Meta WhatsApp Cloud API.
* **Duration:** For the duration of the Principal Agreement / Subscription.
* **Categories of Data Subjects:** Customers, prospective leads, and employees/agents of the Data Controller.
* **Types of Personal Data:** Names, WhatsApp phone numbers (E.164), chat messages, interactive button choices, trade quote specifications, and audio voice messages.

---

## 3. Obligations and Rights of the Data Controller

1. The Data Controller confirms that it has lawful grounds (e.g., consent, contract fulfillment, or legitimate interest) to collect and process personal data and instruct the Processor.
2. The Data Controller retains sole responsibility for the accuracy, quality, and legality of personal data provided to the Processor.

---

## 4. Obligations of the Data Processor

The Data Processor agrees to:
1. **Process Only on Documented Instructions:** Process personal data solely in accordance with documented instructions from the Controller, unless required by applicable EU or Swiss law.
2. **Confidentiality:** Ensure that all personnel authorized to process personal data are committed to strict confidentiality obligations.
3. **Security of Processing (Art. 32 GDPR):** Implement state-of-the-art Technical and Organizational Measures (TOMs), detailed in Annex 1.
4. **Sub-processors:** Engage sub-processors only in accordance with Section 5 of this DPA.
5. **Assistance to the Controller:** Provide reasonable assistance in fulfilling data subject rights requests (access, erasure, rectification) and data breach notifications.
6. **Data Deletion / Return:** Upon termination of services, delete or return all personal data within 30 days, unless statutory retention obligations apply.

---

## 5. Authorized Sub-Processors

The Data Controller grants general written authorization to engage the following sub-processors:

| Sub-Processor | Role | Location | Security / Compliance |
| :--- | :--- | :--- | :--- |
| **Meta Platforms Ireland Ltd.** | WhatsApp Cloud API Infrastructure | Ireland / EU | GDPR Data Processing Addendum |
| **Stripe Payments Europe Ltd.** | Payment & Subscription Billing | Ireland / EU | PCI-DSS Level 1 / GDPR Compliant |
| **Google Cloud Platform** | AI Inference (Gemini Models) | Frankfurt / EU | ISO 27001, SOC 2, SCCs |
| **Mistral AI SAS** | EU-Residency AI Inference | Paris / EU | GDPR Compliant, EU Hosting |
| **Deepgram, Inc.** | Voice Transcription Services | EU / USA | SOC 2 Type II, SCCs |

---

## Annex 1: Technical & Organizational Measures (TOMs)

1. **Access Control:** Multi-factor authentication (2FA) enforced on all administrative and developer accounts.
2. **Database Isolation:** Multi-tenant PostgreSQL database secured with Row-Level Security (RLS) ensuring strict isolation across tenant partitions.
3. **Encryption:**
   * **In Transit:** TLS 1.3 encryption enforced across all API endpoints, webhooks, and UI assets.
   * **At Rest:** AES-256 encryption applied to all database storage and backups.
4. **Webhook Security:** HMAC-SHA256 signature verification (`X-Hub-Signature-256` and Stripe signatures) on all inbound webhook payloads.
5. **Service Window Guard:** Deterministic enforcement preventing outbound messaging outside the customer-initiated 24-hour service window.
