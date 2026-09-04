import re
import time
import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppStoreAgent:
    """Enterprise-grade consultative sales intelligence agent for retail businesses on WhatsApp."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    # ------------------------------------------------------------------
    # Master Sales Intelligence Prompt (23-Point Consultative Framework)
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        business_name: str,
        industry: str,
        catalog_context: str,
        spec_context: str = "",
        business_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        spec_section = f"\n=== OFFICIAL MANUFACTURER SPECS (LOOKED UP) ===\n{spec_context}\n" if spec_context else ""
        
        prof = business_profile or {}
        address = prof.get("address", "")
        city = prof.get("city", "")
        instagram_url = prof.get("instagram_url", "")
        youtube_url = prof.get("youtube_url", "")
        maps_url = prof.get("google_maps_url", "")

        profile_section = f"""
=== VERIFIED BUSINESS PROFILE & OFFICIAL CHANNELS (DATABASE TRUTH) ===
Official Physical Address: {address}
City: {city}
Google Maps Navigation: {maps_url}
Official Instagram: {instagram_url}
Official YouTube Channel: {youtube_url}
""" if (address or instagram_url or youtube_url) else ""

        return f"""You are the expert Sales Consultant for {business_name}, a premier dealer in Pakistan ({industry}).
You communicate with buyers on WhatsApp using a consultative, relationship-first approach.
{profile_section}
=== 1. CORE BEHAVIOR & SALES PROCESS ===
- You are an expert, knowledgeable firearms sales consultant in Pakistan. Be warm, natural, and helpful.
- For every customer message:
  1. Carefully read what the customer is actually asking or saying in THIS conversation.
  2. Answer directly based on verified inventory, business profile, and specs.
  3. Keep responses natural, conversational, and helpful.
- CATEGORY, ORIGIN & CALIBER INTELLIGENCE:
  * When asked about a specific origin (e.g. "Russian rifles", "American guns", "Austrian pistols", "Turkish shotguns"):
    Filter the catalog by that country/origin and recommend the matching items with prices (e.g. Russian -> Saiga MK, Vepr Molot, Baikal Makarov).
  * When asked about a category (e.g. "pistols hain?", "rifles dikhao", "shotgun available hai?"):
    List the top popular models in that category from the catalog with prices.
  * When asked for recommendations / caliber advice (e.g. "9mm mai konse ache hain?", "concealed carry ke liye kya behtar hai?", "best rifle konsi hai?"):
    Brainstorm and recommend 2-4 top choices from the catalog (e.g. for 9mm: Glock 19 Gen 5, Canik TP9, Taurus G3) explaining briefly why they are popular (reliability, ergonomics, value for money).
  * If the customer corrects you (e.g. "russian ka pocha hai?"):
    Acknowledge gracefully and answer their exact specific query from the catalog.
- If the customer asks about COLORS, VARIANTS, or FINISHES (e.g. "colors isme konse available hain", "fde hai ya black?", "wood stock hai?"):
  * Be consultative and knowledgeable: describe available finishes (e.g. Standard Matte Black, Cerakote FDE / Desert Tan, Satin Chrome / Nickel, or Wood furniture for AK/Vepr).
  * Ask which finish or color they prefer!
  * NEVER assume delivery and NEVER escalate to management for color/variant questions.
- If the customer shows interest in buying a product (e.g. "19x lagegi", "glock chahiye", "ye lena hai"):
  * Acknowledge positively with the price: "Zabardast choice hai, Glock 19X Austria brand new available hai PKR 550,000 mein. Aap shop visit karke purchase karna chahenge ya delivery chahiye?"
  * NEVER assume they want delivery or assume their city unless they explicitly mentioned it.

=== 2. STORE LOCATION, PHYSICAL VISIT & SOCIAL MEDIA CHANNELS ===
- When customer asks about physical location, shop address, or visiting the store in ANY phrasing (e.g. "shop kahan hai", "location bhejo", "visit karna hai address do", "dukan kidhar hai", "peshawar mein kahan hain", "store address kya hai"):
  * Answer directly, warmly and accurately with the verified physical address: "{address}"
  * Share the Google Maps link naturally so they can navigate easily: "{maps_url}"
  * Welcoming tone: "Aap bilkul shop visit kar sakte hain, yeh hamara address hai: {address}"
  * NEVER claim you don't know the address, and NEVER escalate shop visit/address inquiries to management!
- When customer asks about social media channels, videos, reviews, or Instagram/YouTube in ANY phrasing (e.g. "instagram link do", "insta id kya hai", "youtube channel hai?", "videos kahan dekh sakta hoon", "online page dikhao"):
  * Answer warmly and share the verified links directly from the profile:
    - Instagram: {instagram_url}
    - YouTube: {youtube_url}
  * If they specifically asked for Instagram, give the Instagram link. If YouTube/videos, give the YouTube link. If general social channels, share both!
  * NEVER invent URLs or use placeholders.

=== 3. STRICT CONVERSATION RULES ===
1. NO HALLUCINATION OF NAMES OR CITIES:
   - NEVER invent or guess a customer name. Only use a name if the customer explicitly introduced themselves (e.g. "Mera naam Usman hai"). Otherwise do NOT use any name.
   - NEVER invent or guess a city. Only mention a city if the customer explicitly stated it in their message.
2. NATURAL HUMAN DIALOGUE & FOLLOW-UPS:
   - When greeted ("salam", "hello", "hi", "aoa", "kese ho"):
     "Walaikum Assalam! {business_name} se baat kar raha hoon, batayein kis cheez ki talash hai?"
   - When customer says "ok", "theek hai", "shukriya", "acha":
     "Jee theek hai bhai!" (or offer help if appropriate).
   - If the customer asks what you are confirming (e.g. "kia confirm ker rahay?", "kya pata kar rahe ho?"):
     Explain naturally like a human: "Bhai aapki delivery charges aur availability shop se confirm kar raha hoon, jaise hi pata chalta hai aapko batata hoon. Is ke ilawa kisi aur cheez ki details chahiyein?"
   - If customer asks for ALTERNATIVES or OTHER OPTIONS (e.g. "or options nahi hain?", "kuch aur dikhao", "dusre models bata"):
     List 3-5 different models from the catalog with prices. Be consultative and helpful.
3. PHOTO & PICTURE REQUESTS:
   - When the customer asks to see a picture or photo of a firearm (e.g. "pic dikhayein", "photo bhejo", "tasweer dekhni hai", "iski picture"):
     Reply warmly and concisely: "Jee bilkul, yeh check karein." or "Jee bhai, yeh lijiye picture." (The system automatically attaches and delivers the actual product photo).
     NEVER claim you cannot send photos or do not have the option.
4. PLAIN TEXT ONLY (NO EMOJIS, NO MARKDOWN):
   - Zero emojis.
   - No asterisks (*bold*), bullets, or headers. Write like a normal person typing on WhatsApp.
5. PAKISTANI ROMAN URDU ONLY:
   - Zero Devanagari/Hindi script. Natural Pakistani Roman Urdu (English letters) or Urdu script.

=== 4. WHEN TO ESCALATE TO MANAGEMENT (STRICT RULES) ===
Only escalate when the customer asks something you cannot answer from verified catalog:
- Delivery charges for a specific city: If customer asks "delivery charges kya hain?" without stating their city, ask: "Delivery bilkul arrange ho sakti hai. Aap kis city mein mangwana chahte hain?"
- Once the customer names their city for delivery (e.g. "Islamabad delivery chahiye"):
  Tell them: "Theek hai, main shop management se confirm karke aapko foran delivery charges batata hoon."
  Include internal tag: [ESCALATE: delivery]
- LEGAL / LICENSING / REGULATORY QUESTIONS:
  * NEVER give legal advice or speculate on license validity.
  * Tell them: "Firearms purchase ke liye valid license aur legal requirements zaroori hain. Iski exact procedure aur verification ke liye main shop management se confirm karke aapko update karta hoon."
  * Include internal tag: [ESCALATE: legal]
- Custom discount / price bargaining:
  Tell them: "Theek hai, main shop se confirm karke aapko foran update karta hoon."
  Include internal tag: [ESCALATE: discount]
{spec_section}
=== VERIFIED STORE CATALOG & INVENTORY ===
{catalog_context}
"""

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting, decorative emoji spam, and Devanagari script."""
        if re.search(r'[\u0900-\u097F]', text):
            hindi_fixes = {
                'जानी': 'jaani', 'जाती': 'jaati', 'है': 'hai', 'हैं': 'hain',
                'के': 'ke', 'کی': 'ki', 'کا': 'ka', 'में': 'mein', 'से': 'se',
                'को': 'ko', 'पर': 'par', 'नहीं': 'nahi', 'भी': 'bhi', 'और': 'aur',
                'यह': 'yeh', 'वह': 'woh', 'आप': 'aap', 'लिए': 'liye', 'किया': 'kiya',
                'गया': 'gaya', 'थी': 'thi', 'था': 'tha', 'थे': 'the'
            }
            for h_word, r_word in hindi_fixes.items():
                text = text.replace(h_word, r_word)
            text = re.sub(r'[\u0900-\u097F]+', '', text)

        text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)  # *bold* and **bold**
        text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)    # _italic_ and __italic__
        text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)  # ### headers
        text = re.sub(r'^[-*•]\s+', '', text, flags=re.MULTILINE)    # bullet points
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)    # numbered lists
        text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)               # code blocks
        text = re.sub(r'\n{3,}', '\n\n', text)                       # excess newlines

        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F'
            r'\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F'
            r'\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+'
        )
        text = emoji_pattern.sub('', text)
        return text.strip()

    @staticmethod
    def _chunk_reply(text: str, max_chars: int = 280) -> List[str]:
        if len(text) <= max_chars:
            return [text]

        chunks: List[str] = []
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_chars:
                current = f"{current}\n{para}" if current else para
            else:
                if current:
                    chunks.append(current)
                if len(para) <= max_chars:
                    current = para
                else:
                    sentences = re.split(r'([.!?]\s+)', para)
                    s_current = ""
                    for s in sentences:
                        if len(s_current) + len(s) <= max_chars:
                            s_current += s
                        else:
                            if s_current.strip():
                                chunks.append(s_current.strip())
                            s_current = s
                    current = s_current.strip()

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text]

    async def handle_customer_interaction(
        self,
        customer_message: str,
        business_name: str,
        industry: str,
        catalog_context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        image_bytes: Optional[bytes] = None,
        image_base64: Optional[str] = None,
        tenant_id: Optional[str] = None,
        business_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Runs the Gemini sales agent with strictly grounded context."""
        request_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()

        # Load business profile dynamically from database if not provided
        if tenant_id and not business_profile:
            try:
                from app.services.catalog_tools import get_business_profile
                business_profile = await get_business_profile(tenant_id)
            except Exception as e:
                logger.warning("[%s] Could not load business_profile: %s", request_id, e)

        # Check if customer is asking a detailed technical spec question about a catalog item
        spec_context = ""
        is_spec_query = any(w in customer_message.lower() for w in ["specs", "spec", "barrel", "weight", "length", "twist", "dimension", "finish", "material"])
        if is_spec_query:
            try:
                from app.services.spec_search import search_product_specs
                from app.graph.nodes.nlu import _BRANDS, _catalog_cache, _refresh_catalog_cache_if_needed
                await _refresh_catalog_cache_if_needed()
                # Find candidate product
                cand_p = None
                cm_lower = customer_message.lower()
                for p_name in sorted(_catalog_cache, key=len, reverse=True):
                    if p_name in cm_lower:
                        cand_p = p_name.title()
                        break
                if not cand_p:
                    for b_name, d_model in sorted(_BRANDS.items(), key=lambda x: len(x[0]), reverse=True):
                        if b_name in cm_lower:
                            cand_p = d_model
                            break
                if not cand_p and conversation_history:
                    # check last assistant mention
                    for h in reversed(conversation_history):
                        h_lower = h.get("text", "").lower()
                        for p_name in sorted(_catalog_cache, key=len, reverse=True):
                            if p_name in h_lower:
                                cand_p = p_name.title()
                                break
                        if cand_p:
                            break
                if cand_p:
                    spec_context = await search_product_specs(cand_p, customer_message)
                    if spec_context:
                        logger.info("[%s] Looked up manufacturer specs for %s: %s", request_id, cand_p, spec_context[:100])
            except Exception as spec_err:
                logger.warning("[%s] Spec search error: %s", request_id, spec_err)

        system_instruction = self._build_system_prompt(
            business_name=business_name,
            industry=industry,
            catalog_context=catalog_context,
            spec_context=spec_context,
            business_profile=business_profile,
        )

        contents = []
        # Only include the last 6 messages to keep context fresh and avoid stale name/city bias
        fresh_history = (conversation_history or [])[-6:]
        for item in fresh_history:
            role = "user" if item.get("role") == "customer" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=item["text"])],
                )
            )

        user_text = customer_message or "Ye photo mein konsi product hai aur iski price kya hai?"
        user_parts = []

        if image_bytes:
            user_parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        elif image_base64:
            try:
                import base64
                decoded_bytes = base64.b64decode(image_base64)
                user_parts.append(types.Part.from_bytes(data=decoded_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning("[%s] Could not decode image_base64: %s", request_id, e)

        user_parts.append(types.Part.from_text(text=user_text))

        contents.append(
            types.Content(
                role="user",
                parts=user_parts,
            )
        )

        try:
            import asyncio
            response = None
            for attempt in range(2):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.5,
                            max_output_tokens=350,
                        ),
                    )
                    break
                except Exception as gen_err:
                    if attempt == 0 and ("503" in str(gen_err) or "overload" in str(gen_err).lower()):
                        logger.warning("[%s] Gemini 503/overload on attempt 1, retrying after 1.5s...", request_id)
                        await asyncio.sleep(1.5)
                        continue
                    raise

            try:
                reply_text = response.text.strip() if response.text else ""
            except Exception as text_err:
                logger.warning("[%s] Gemini response blocked: %s", request_id, text_err)
                reply_text = ""

            if not reply_text:
                reply_text = "Jee bataiye, kis firearm model ya product ke baare mein janna chahte hain?"

            # Detect escalation tag from model
            needs_escalation = False
            extracted_item = None
            extracted_city = None
            extracted_name = None

            if "[ESCALATE" in reply_text:
                needs_escalation = True
                reply_text = re.sub(r'\[ESCALATE:?[^\]]*\]', '', reply_text, flags=re.IGNORECASE).strip()

            # Strictly inspect only the current message + last 2 customer turns for facts.
            recent_customer_turns = [h.get("text", "") for h in fresh_history if h.get("role") == "customer"][-2:]
            customer_recent_text = customer_message + " " + " ".join(recent_customer_turns)
            lower_all = customer_recent_text.lower()
            lower_cust = lower_all

            # Extract Name ONLY if explicitly stated with valid introduction pattern
            INVALID_NAME_WORDS = {
                "nahi", "nahin", "brand", "pata", "naam", "firearm", "pistol", "gun", "rifle",
                "delivery", "lahore", "karachi", "islamabad", "rawalpindi", "peshawar",
                "glock", "taurus", "hai", "bhai", "want", "need", "price", "pindi",
                "unknown", "koi", "kuch", "shukriya", "insta", "instagram", "page", "dekha"
            }
            name_match = re.search(r'\b(?:mera naam|my name is|i am)\s+([a-zA-Z]{3,15})\b', lower_cust)
            if name_match:
                cand = name_match.group(1).capitalize()
                if cand.lower() not in INVALID_NAME_WORDS:
                    extracted_name = cand

            # Extract City ONLY if explicitly stated in recent customer messages
            for city in ["lahore", "karachi", "islamabad", "rawalpindi", "peshawar", "quetta", "multan", "faisalabad", "sialkot", "gujranwala", "abbottabad", "mardan", "kohat"]:
                if re.search(rf'\b{city}\b', lower_cust):
                    extracted_city = city.capitalize()
                    break

            # Extract Product
            search_corpus = lower_all
            recent_assistant_text = " ".join([h.get("text", "") for h in fresh_history if h.get("role") != "customer"][-2:]).lower()
            if image_bytes or image_base64 or not lower_all.strip() or any(w in lower_all for w in ["image", "picture", "photo", "tasweer", "share"]):
                search_corpus = f"{lower_all} {reply_text.lower()} {recent_assistant_text}"

            if catalog_context:
                for line in catalog_context.split("\n"):
                    line_clean = line.strip().lstrip("-").strip()
                    if ":" in line_clean:
                        p_name = line_clean.split(":")[0].strip()
                        if p_name and p_name.lower() in search_corpus:
                            extracted_item = p_name
                            break

            if not extracted_item:
                from app.graph.nodes.nlu import _BRANDS, _catalog_cache
                for model in sorted(_catalog_cache, key=len, reverse=True):
                    if re.search(rf'\b{re.escape(model)}\b', search_corpus):
                        extracted_item = model.title()
                        break
                if not extracted_item:
                    for brand, default_model in sorted(_BRANDS.items(), key=lambda x: len(x[0]), reverse=True):
                        if re.search(rf'\b{re.escape(brand)}\b', search_corpus):
                            extracted_item = default_model
                            break

            # Only escalate delivery if the customer EXPLICITLY asked for delivery (not store visit or address)
            is_delivery_asked = (
                any(k in customer_message.lower() for k in ["delivery", "deliver", "bhej", "charges", "charges honge", "kitne din"])
                and not any(k in customer_message.lower() for k in ["visit", "shop", "dukan", "address", "location", "kahan", "kidhar", "insta", "youtube"])
            )
            if is_delivery_asked and extracted_city:
                needs_escalation = True

            # Escalate discount / custom price requests to shop management
            is_discount_asked = any(k in customer_message.lower() for k in ["discount", "kam ho", "kam hoga", "gunjaish", "gunjash", "final price", "kam rate"]) or ("mil sakta hai" in customer_message.lower() and any(w in customer_message.lower() for w in ["mein", "mai", "lakh", "hazar", "price", "rate"]))
            if is_discount_asked:
                needs_escalation = True
                if not any(k in reply_text.lower() for k in ["confirm karke", "pata karke", "management"]):
                    reply_text = "Theek hai bhai, main shop management se confirm karke aapko foran update karta hoon."

            # Escalate legal / licensing inquiries
            from app.graph.nodes.nlu import _has_legal_intent
            if _has_legal_intent(customer_message):
                needs_escalation = True
                if not any(k in reply_text.lower() for k in ["confirm karke", "license zaroori", "management"]):
                    reply_text = "Firearms purchase ke liye valid license aur legal requirements zaroori hain. Iski exact procedure aur verification ke liye main shop management se confirm karke aapko update karta hoon."

            reply_text = self._strip_markdown(reply_text)
            chunks = self._chunk_reply(reply_text)

            is_order_intent = any(
                kw in customer_message.lower()
                for kw in ["order", "book", "kharidna", "lena hai", "confirm order", "lagegi", "chahiye"]
            )

            latency = int((time.monotonic() - t0) * 1000)
            logger.info(
                "[%s] Gemini OK — %d chunks, %dms, escalate=%s (item=%s, city=%s)",
                request_id, len(chunks), latency, needs_escalation, extracted_item, extracted_city
            )

            return {
                "reply_text": reply_text,
                "reply_chunks": chunks,
                "is_order_intent": is_order_intent,
                "needs_escalation": needs_escalation,
                "extracted_name": extracted_name,
                "extracted_item": extracted_item,
                "extracted_city": extracted_city,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "gemini",
            }

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[STORE_AGENT ERROR] {e}\n{tb}", flush=True)
            latency = int((time.monotonic() - t0) * 1000)
            cm_lower = (customer_message or "").lower()
            if any(w in cm_lower for w in ["salam", "hello", "hi", "aoa", "koi hai", "kese ho", "kia haal", "kia hal", "assalam"]):
                fallback = f"Walaikum Assalam! Jee bhai, {business_name} se rabta karne ka shukriya. Batayein kis firearm model ya product ke baare mein maloomat chahiye?"
            elif any(w in cm_lower for w in ["shop", "address", "location", "visit", "kahan"]):
                addr = (business_profile or {}).get("address", "Shop 4, Haider Arms, Old Fruit Market, GT Road, Sikander Town, Peshawar, 25000")
                maps = (business_profile or {}).get("google_maps_url", "https://maps.google.com/?q=Shop+4+Haider+Arms+Old+Fruit+Market+GT+Road+Sikander+Town+Peshawar+25000")
                fallback = f"Aap bilkul shop visit kar sakte hain, yeh hamara address hai: {addr}.\n\nGoogle Maps link: {maps}\n\nJab bhi aana ho bataiyega, hum aapko facilitate kar denge!"
            else:
                fallback = f"Jee bhai, {business_name} mein khushamdeed! Batayein kis model ya firearm ki details chahiyein?"
            return {
                "reply_text": fallback,
                "reply_chunks": [fallback],
                "is_order_intent": False,
                "needs_escalation": False,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "fallback_graceful",
            }
