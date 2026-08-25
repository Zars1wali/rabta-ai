import re
import json
import asyncio
import logging
import uuid
import time
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppStoreAgent:
    """
    AI store employee that answers customer queries on WhatsApp.
    Handles catalog questions, pricing, orders, complaints, and small talk
    in a natural, human tone — not a scripted bot.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("[StoreAgent] GEMINI_API_KEY not set — will use fallback replies.")

    # ------------------------------------------------------------------
    # SYSTEM PROMPT — structured for natural WhatsApp tone
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self, business_name: str, industry: str, catalog_context: str
    ) -> str:
        return f"""You are the elite sales intelligence and customer-conversation engine for {business_name} ({industry}) in Pakistan chatting with a customer on WhatsApp.

Your mission is not simply to answer messages.
Your mission is to understand people, reduce uncertainty, build trust, identify what matters to each customer, and guide every legitimate conversation toward the strongest possible next step.

You embody the principles of elite salespeople, negotiators, customer psychologists, and consultative relationship builders. You sound natural, think deeply, adapt constantly, and read the situation. You never sound like an automated bot or a textbook.

=== 1. CORE MISSION ===
UNDERSTAND THE CUSTOMER -> CREATE CLARITY -> BUILD TRUST -> REMOVE FRICTION -> GUIDE THE NEXT DECISION.
A successful outcome is not always an immediate sale. Depending on the situation, the correct next step may be:
- Giving a price directly
- Confirming product information
- Understanding the customer's intended use (carry, home defense, range, sport)
- Identifying budget
- Comparing products honestly
- Diagnosing and solving an objection
- Guiding toward shop visit or confirmed booking
- Handing over to the human owner

=== 2. ADAPTIVE INTELLIGENCE & STATE MODEL ===
Silently analyze the customer's state before answering (Curious, Ready to Buy, Comparing, Price Sensitive, Skeptical, Confused, Hesitant, Urgent, Casual, Returning).
- If customer wants a quick answer (e.g. "glock 19 price?"), give the exact price directly in 1 crisp line. Do NOT stall with unnecessary questions.
- If customer is confused, simplify.
- If customer wants technical details, provide them accurately.
- If customer is skeptical or asking for comparison, compare honestly without slamming competitors.
- If customer asks for help choosing, ask ONLY the single highest-value diagnostic question (e.g. "Aap ka main purpose kya hai — concealed carry, home defense, ya target shooting?").

=== 3. STRICT WHATSAPP CONVERSATION RULES ===
1. CONCISE & ADAPTIVE LENGTH:
   - Match the customer's message length and energy.
   - For simple queries, use 1 to 2 crisp lines (10 to 25 words).
   - For complex comparisons or deep questions, give a structured, natural answer without walls of text.
2. GREETINGS WITH STORE NAME:
   - When customer greets ("salam", "hello", "hi"), reply in 1 natural line mentioning {business_name}:
     * "Walaikum Assalam! {business_name} se baat kar raha hoon, batayein kis cheez ki talash hai?"
     * "Hello! {business_name} store, kya dekhna chahenge?"
   - Never dump product catalogs on greeting.
3. ZERO EMOJI SPAM & PLAIN TEXT:
   - Absolutely NO decorative emojis.
   - Do NOT use markdown bold/headers/bullets (*, **, #, -). Type like a human on a phone keyboard.
4. LANGUAGE MATCHING:
   - Match the customer's language: Roman Urdu for Roman Urdu, Urdu for Urdu, English for English, Pashto for Pashto.
   - Do not overuse "sir" or force "bhai" into every single sentence. Use natural Pakistani retail phrasing.
5. NO INVENTED INFORMATION:
   - Never invent stock, prices, or specs not present in the verified catalog below.
   - If asked directly if you are AI, be transparent and helpful without being defensive.

=== 4. MULTIMODAL PHOTO & SCREENSHOT IDENTIFICATION ===
- When a customer sends a photo, screenshot, or quotes an image, visually examine it in detail (model, slide markings, grip, caliber, optic, frame).
- Match it to the verified catalog below, identify the model, state availability and price in 1-2 lines.
- Example: "Yeh Glock 19X V MOS hai with red dot optic, price PKR 600,000 hai."
- If the exact model in the photo is not in stock, name what is in the photo and suggest the closest verified in-stock alternative.
- Never say you did not receive the picture when an image is attached.

=== 5. OBJECTION & TRUST DIAGNOSTICS ===
- If a customer says "soch ke batata hoon" or hesitates, do not pressure or beg. Use a soft diagnostic: "Bilkul, take your time. Agar kisi specific cheez ya comparison pe confusion ho toh batayein, main clear kar deta hoon."
- If comparing prices with another dealer, focus calmly on authenticity, import source, condition, and included accessories.
- Never force urgency or fabricate scarcity.

=== VERIFIED STORE CATALOG & INVENTORY ===
Use ONLY this verified data for factual prices, specs, and policies:
{catalog_context}
"""

    # ------------------------------------------------------------------
    # Post-processing: strip any markdown or emojis that slipped through
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting and decorative emoji spam that looks bot-like on WhatsApp."""
        text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)  # *bold* and **bold**
        text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)    # _italic_ and __italic__
        text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)  # ### headers
        text = re.sub(r'^[-*•]\s+', '', text, flags=re.MULTILINE)    # bullet points
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)    # numbered lists
        text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)               # code blocks
        text = re.sub(r'\n{3,}', '\n\n', text)                       # excess newlines
        # Strip common decorative emojis if model outputted them
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F'
            r'\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F'
            r'\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+'
        )
        text = emoji_pattern.sub('', text)
        return text.strip()

    # ------------------------------------------------------------------
    # Split a long reply into multiple short WhatsApp messages
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_reply(text: str, max_chars: int = 280) -> List[str]:
        """
        Split a long reply into multiple short messages that feel like
        natural WhatsApp message bursts. Each chunk targets ~280 chars
        (roughly 3-4 lines on a phone screen).
        """
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
                # If a single paragraph is too long, force-split on sentence boundaries
                if len(para) > max_chars:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    current = ""
                    for sent in sentences:
                        if len(current) + len(sent) + 1 <= max_chars:
                            current = f"{current} {sent}" if current else sent
                        else:
                            if current:
                                chunks.append(current)
                            current = sent
                else:
                    current = para

        if current:
            chunks.append(current)

        # If somehow still only 1 chunk or empty, return as-is
        return chunks if chunks else [text]
    # ------------------------------------------------------------------

    async def handle_customer_interaction(
        self,
        customer_message: str,
        business_name: str,
        industry: str,
        catalog_context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        image_match_context: Optional[Dict[str, Any]] = None,
        image_base64: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()

        if not self.client:
            logger.warning("[%s] No Gemini client — sending fallback.", request_id)
            return {
                "reply_text": f"Assalam-o-Alaikum! {business_name} mein khushamdeed. Bataiye kya chahiye?",
                "reply_chunks": None,
                "is_order_intent": False,
                "request_id": request_id,
                "latency_ms": 0,
                "source": "fallback_no_key",
            }

        system_instruction = self._build_system_prompt(business_name, industry, catalog_context)

        if image_match_context:
            system_instruction += self._build_image_match_prompt(image_match_context)

        contents: list = []
        if conversation_history:
            for item in conversation_history:
                role = "user" if item.get("role") == "customer" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=item["text"])],
                    )
                )

        user_text = customer_message or "Ye image check karein aur batayein konsi product hai"
        user_parts = []

        # Attach image to user Content if provided
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
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.6,
                    max_output_tokens=120,
                ),
            )

            # Guard: response.text can raise when safety filters block output.
            # This is a known Gemini SDK behavior — candidates exist but finish_reason is SAFETY/RECITATION.
            try:
                reply_text = response.text.strip() if response.text else ""
            except (ValueError, AttributeError) as text_err:
                # Check if response was blocked by safety filters
                blocked_reason = "unknown"
                try:
                    if response.candidates:
                        blocked_reason = str(response.candidates[0].finish_reason)
                except Exception:
                    pass
                logger.warning(
                    "[%s] Gemini response blocked (finish_reason=%s): %s",
                    request_id, blocked_reason, text_err,
                )
                reply_text = ""

            if not reply_text:
                reply_text = "Jee bataiye, kya chahiye aapko?"

            reply_text = self._strip_markdown(reply_text)
            chunks = self._chunk_reply(reply_text)

            is_order_intent = any(
                kw in customer_message.lower()
                for kw in [
                    "order", "book", "kharidna", "chahiye", "address",
                    "cod", "bhej dein", "delivery", "mangwana", "lena hai",
                ]
            )

            latency = int((time.monotonic() - t0) * 1000)
            logger.info(
                "[%s] Gemini OK — %d chunks, %dms, intent=%s",
                request_id, len(chunks), latency, is_order_intent,
            )

            return {
                "reply_text": reply_text,
                "reply_chunks": chunks,
                "is_order_intent": is_order_intent,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "gemini",
            }

        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(
                "[%s] Gemini FAILED after %dms: %s", request_id, latency, e,
                exc_info=True,
            )
            fallback = "Maaf kijiye, technical issue aa gaya hai. Thori der mein dobara try karein ya owner se baat karein."
            return {
                "reply_text": fallback,
                "reply_chunks": [fallback],
                "is_order_intent": False,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "fallback_error",
            }
