# Meta Tech Provider & WhatsApp App Review Submission Guide

**Application Name:** Nuncio  
**App ID:** `1584644373301704`  
**Business Portfolio:** `zeropointintel` (`1188005875832676`)  
**Applicant / Developer:** Nuno Miguel Pires Ribeiro (ZeroPointIntel)  
**Target Capabilities:** Meta Tech Provider, WhatsApp Embedded Signup, Automated Customer Communication  

---

## 1. Overview of Requested Permissions

To enable seamless onboarding of merchants and automated conversational support via the WhatsApp Cloud API, Nuncio requires **Advanced Access** for two specific permissions:

1. **`whatsapp_business_management`**
2. **`whatsapp_business_messaging`**

---

## 2. Exact Answers for Meta App Review Form

### Permission 1: `whatsapp_business_management`

#### Question: "How does your app use whatsapp_business_management?"
> **Submission Text:**
> "Nuncio is a B2B SaaS platform and Meta Tech Provider that provides automated sales qualification, quote extraction, and customer support for commercial merchants (service trades and e-commerce businesses).
>
> We use the `whatsapp_business_management` permission to allow our business customers to onboard their WhatsApp Business Accounts (WABAs) and phone numbers into Nuncio via the Meta Embedded Signup flow. Through this permission, our platform:
> 1. Completes the Embedded Signup handshake to securely link the merchant's WABA and phone number to their Nuncio workspace.
> 2. Verifies phone number connectivity and status using the Graph API (`GET /{phone-number-id}`).
> 3. Registers two-step verification PINs (`POST /{phone-number-id}/register`) to activate Cloud API messaging.
>
> This permission is strictly used for administrative onboarding and management of customer WABAs with explicit merchant authorization."

---

### Permission 2: `whatsapp_business_messaging`

#### Question: "How does your app use whatsapp_business_messaging?"
> **Submission Text:**
> "Our platform uses `whatsapp_business_messaging` to enable automated conversational messaging between our merchant clients and their end customers on WhatsApp.
>
> Specifically, our app:
> 1. Receives inbound customer messages, inquiries, and voice notes via webhook events (`messages` webhook).
> 2. Parses customer requests (such as service quote requests, dimensions, service frequency, or product inquiries) and passes them to our grounded AI engine.
> 3. Sends immediate, deterministic, and helpful replies to the customer on behalf of the merchant (`POST /{phone-number-id}/messages`).
> 4. Dispatches interactive reply buttons (e.g., service selection, appointment confirmations) to streamline customer qualification.
> 5. Strictly abides by the 24-hour customer service window, ensuring no unauthorized outbound messages are dispatched outside active customer-initiated conversations."

---

## 3. Screen Recording Walkthrough Script

Meta reviewers require a clear video recording ($\le 2$ minutes) demonstrating how the app functions.

### Step-by-Step Recording Instructions:

1. **Scene 1: Merchant Log In & Settings (0:00 - 0:25)**
   * Show the Nuncio web dashboard.
   * Navigate to **Settings $\rightarrow$ WhatsApp Connection**.
   * Click **"Connect WhatsApp Business"** button which triggers the Meta Embedded Signup modal / popup.

2. **Scene 2: Meta Embedded Signup Flow (0:25 - 0:50)**
   * Demonstrate the Facebook Login for Business dialog opening.
   * Select a test Business Portfolio and select/create a test WhatsApp Business Account (WABA) and test phone number.
   * Complete the dialog and grant the requested permissions (`whatsapp_business_management` & `whatsapp_business_messaging`).

3. **Scene 3: Status & Connectivity Verification (0:50 - 1:10)**
   * Return to Nuncio dashboard showing the connected Phone Number, WABA ID, and **"CONNECTED"** status badge.
   * Show the webhook subscription active.

4. **Scene 4: Live Inbound & Outbound Messaging (1:10 - 1:45)**
   * Open WhatsApp on a test phone or WhatsApp Web.
   * Send a test message to the connected WhatsApp Business number (e.g., *"Hello, I need a quote for office cleaning"*).
   * Show the incoming message appearing in the Nuncio Unified Inbox.
   * Show the automated AI response being generated and sent back to the customer on WhatsApp with interactive buttons.
   * Conclude by showing the structured lead card created in the Nuncio Lead Board.

---

## 4. App Details & Compliance Checklist Before Submitting

* [x] **Privacy Policy URL:** `https://zeropointintel.com/privacy` (pointing to the verified [PRIVACY_POLICY.md](../../legal/PRIVACY_POLICY.md))
* [x] **Terms of Service URL:** `https://zeropointintel.com/terms` (pointing to [TERMS_OF_SERVICE.md](../../legal/TERMS_OF_SERVICE.md))
* [x] **Data Deletion URL:** `https://zeropointintel.com/privacy#8-user-data-deletion-request-instructions`
* [x] **App Icon:** $1024 \times 1024$ PNG uploaded in App Settings.
* [x] **Business Verification:** Submitted under `Nuno Miguel Pires Ribeiro` with official identity and address proofs.
* [x] **Test Credentials Provided:** Include test login credentials and test phone number in the review notes so the Meta reviewer can test without friction.
