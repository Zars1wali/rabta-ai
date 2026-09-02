import re
import json
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from google import genai
from google.genai import types
from app.core.config import settings
from app.models.database import CatalogItem
from app.db.repositories import catalog_repo, price_log_repo
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PriceUpdateService:
    """Natural-language price update manager for business owners on WhatsApp."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        self._pending_updates: Dict[str, Dict[str, Any]] = {}

    def get_pending_state(self, owner_phone: str) -> Optional[Dict[str, Any]]:
        return self._pending_updates.get(owner_phone)

    def clear_pending_state(self, owner_phone: str) -> None:
        if owner_phone in self._pending_updates:
            del self._pending_updates[owner_phone]

    async def extract_price_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """Use Gemini to detect price update intent and extract product and price."""
        if not self.client:
            return self._regex_fallback_parser(text)

        prompt = f"""You are an entity extraction engine for retail store owners updating product prices via WhatsApp messages.
Analyze this message: "{text}"

Task:
1. Determine if the message is an intent to change/update a product price.
2. Extract:
   - "is_price_update": true/false
   - "product_name": name of the item (e.g. "Glock 19 Gen 5", "Taurus G3")
   - "origin": country/origin if specified in text (e.g. "USA", "Austria", "Turkey", or null)
   - "new_price": numeric price in PKR as float. (450k -> 450000, 3.8 lakh -> 380000, 450,000 -> 450000).

Return STRICT JSON only:
{{
  "is_price_update": boolean,
  "product_name": string or null,
  "origin": string or null,
  "new_price": number or null
}}"""

        try:
            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip() if response.text else ""
            data = json.loads(raw)
            if data.get("is_price_update") and data.get("product_name") and data.get("new_price"):
                return data
            return None
        except Exception as e:
            logger.warning("Gemini price extraction fallback: %s", e)
            return self._regex_fallback_parser(text)

    def _regex_fallback_parser(self, text: str) -> Optional[Dict[str, Any]]:
        price_match = re.search(r'(?:price|ab|to|kardo|rate)?\s*(?:pkr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(k|lakh|lac)?(?:\s*(?:ka|ki|kardo|krdo|hai))?', text, re.IGNORECASE)
        if not price_match:
            return None

        raw_val = float(price_match.group(1))
        unit = (price_match.group(2) or "").lower()
        if unit == "k":
            price = raw_val * 1000
        elif unit in ["lakh", "lac"]:
            price = raw_val * 100000
        else:
            price = raw_val

        prod_text = text[:price_match.start()].strip()
        prod_text = re.sub(r'^(?:update|change|set|price of)\s+', '', prod_text, flags=re.IGNORECASE).strip()
        if not prod_text:
            return None

        origin = None
        for org in ["USA", "Austria", "Turkey", "Pakistan", "Brazil", "China", "Italy"]:
            if re.search(rf'\b{org}\b', text, re.IGNORECASE):
                origin = org
                break

        return {
            "is_price_update": True,
            "product_name": prod_text,
            "origin": origin,
            "new_price": price
        }

    async def match_catalog_items(
        self, session: AsyncSession, tenant_id: uuid.UUID, product_name: Optional[str], origin: Optional[str] = None
    ) -> List[CatalogItem]:
        if not product_name or not str(product_name).strip():
            return []

        items = await catalog_repo.get_catalog_for_tenant(session, tenant_id)
        if not items:
            return []

        clean_query = str(product_name or "").lower().strip()

        exact_matches = [
            it for it in items
            if it.name and it.name.lower().strip() == clean_query
        ]
        if origin:
            exact_origin = [
                it for it in exact_matches
                if (it.metadata_json.get("origin") or "").lower() == str(origin).lower()
            ]
            if exact_origin:
                return exact_origin

        if exact_matches:
            return exact_matches

        tokens = [t for t in re.split(r'[\s\-_]+', clean_query) if len(t) > 1 and t not in ['gen', 'price', 'hai', 'ka', 'ki']]
        matches = []
        for it in items:
            it_name_lower = (it.name or "").lower()
            it_origin = (it.metadata_json.get("origin") or "").lower() if it.metadata_json else ""
            it_brand = (it.metadata_json.get("brand") or "").lower() if it.metadata_json else ""

            all_match = True
            for t in tokens:
                if not (t in it_name_lower or t in it_brand):
                    all_match = False
                    break

            if all_match:
                if origin and str(origin).lower() in it_origin:
                    matches.insert(0, it)
                elif not origin:
                    matches.append(it)

        if matches:
            return matches

        # ── STAGE 3: SEMANTIC / NICKNAME / SLANG MATCHING (Vector + LLM fallback) ──
        # When exact and token matching fails (e.g. "30 bore chota model", "amreeki rifle", "choti pistol")
        return await self._semantic_match_fallback(items, clean_query, origin)

    async def _semantic_match_fallback(
        self, items: List[CatalogItem], query: str, origin: Optional[str] = None
    ) -> List[CatalogItem]:
        """
        Use semantic search and LLM understanding to map shop-floor slang, nicknames,
        calibers, and descriptions to actual catalog products.
        """
        if not items or not query:
            return []

        # 1. Try LLM semantic ranker over the tenant's actual catalog items
        client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        if client:
            catalog_summary = []
            for i, it in enumerate(items):
                meta = it.metadata_json or {}
                org = meta.get("origin", "")
                cal = meta.get("caliber", "")
                cat = it.category or ""
                catalog_summary.append(f"[{i}] {it.name} | Category: {cat} | Origin: {org} | Caliber: {cal} | Price: {it.price}")

            prompt = f"""You are a firearms catalog matching engine for a Pakistani gun store.
The user referred to a firearm using shop-floor slang, nickname, caliber, or informal description: "{query}"
Target Origin (if specified): {origin or 'Any'}

Here is the store's inventory catalog:
{chr(10).join(catalog_summary)}

Task:
Identify the best matching catalog item(s) (indices 0 to {len(items)-1}).
- "30 bore chota model" -> small 30 bore pistol (e.g. Norinco NP-7, Zig 14)
- "amreeki rifle" -> American rifle (e.g. Colt M4, Sig Sauer M400, Diamondback DB15)
- "choti pistol" / "subcompact" -> subcompact pistol (e.g. Canik TP9 Sub Elite, HS9 Subcompact)
- "desi katta" / "turkish shotgun" -> shotguns (e.g. Bellini Magnum, Kral XPS)

Return STRICT JSON only:
{{"matched_indices": [number]}}"""

            try:
                resp = await client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                data = json.loads((resp.text or "").strip())
                idxs = data.get("matched_indices") or []
                matched = [items[idx] for idx in idxs if isinstance(idx, int) and 0 <= idx < len(items)]
                if matched:
                    logger.info("[SemanticMatch] Query '%s' matched to %d items: %s", query, len(matched), [m.name for m in matched])
                    return matched
            except Exception as e:
                logger.warning("[SemanticMatch] LLM semantic match error: %s", e)

        # 2. Vector embedding cosine similarity fallback
        try:
            from app.services.embedding_service import embedding_service
            q_vec = await embedding_service.embed_text(query)
            if q_vec:
                scored = []
                for it in items:
                    meta = it.metadata_json or {}
                    it_text = f"{it.name} {it.category or ''} {meta.get('origin', '')} {meta.get('caliber', '')} {it.description or ''}"
                    it_vec = await embedding_service.embed_text(it_text)
                    if it_vec:
                        dot = sum(a * b for a, b in zip(q_vec, it_vec))
                        norm_a = sum(a * a for a in q_vec) ** 0.5
                        norm_b = sum(b * b for b in it_vec) ** 0.5
                        sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
                        if sim > 0.65:
                            scored.append((sim, it))
                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    return [s[1] for s in scored[:3]]
        except Exception as ve:
            logger.warning("[SemanticMatch] Vector embedding fallback error: %s", ve)

        return []

    def _snapshot_item(self, item: CatalogItem) -> Dict[str, Any]:
        return {
            "id": str(item.id),
            "name": item.name,
            "price": float(item.price),
            "origin": item.metadata_json.get("origin") if item.metadata_json else None,
            "sku": item.metadata_json.get("sku", str(item.id)[:8].upper()) if item.metadata_json else str(item.id)[:8].upper(),
            "category": item.category,
            "metadata_json": item.metadata_json or {},
        }

    async def process_owner_price_message(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        owner_phone: str,
        message_text: str,
        on_cache_invalidate: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        pending = self.get_pending_state(owner_phone)
        lower_msg = message_text.lower().strip()

        # 1. Pending disambiguation
        if pending and pending.get("state") == "AWAITING_DISAMBIGUATION":
            if lower_msg in ["cancel", "no", "nahi", "mat karo", "stop"]:
                self.clear_pending_state(owner_phone)
                return {"reply": "Price update cancelled."}

            matches = pending.get("matches", [])
            selected = None
            num_match = re.search(r'\b([1-9])\b', lower_msg)
            if num_match:
                idx = int(num_match.group(1)) - 1
                if 0 <= idx < len(matches):
                    selected = matches[idx]

            if not selected:
                for m in matches:
                    org = (m.get("origin") or "").lower()
                    if org and org in lower_msg:
                        selected = m
                        break

            if not selected:
                return {"reply": f"Samajh nahi aaya. Please 1 se {len(matches)} ke darmiyan number reply karein ya 'cancel' likhein."}

            new_price = pending["proposed_price"]
            pending["state"] = "AWAITING_CONFIRMATION"
            pending["selected_item"] = selected

            origin_str = f" ({selected['origin']})" if selected.get("origin") else ""
            old_p_str = f"PKR {int(selected['price']):,}"
            new_p_str = f"PKR {int(new_price):,}"

            return {
                "reply": f"Confirm: update {selected['name']}{origin_str}, from {old_p_str} to {new_p_str}?\n\nReply 'haan' / 'yes' to confirm or 'cancel'."
            }

        # 2. Pending confirmation
        if pending and pending.get("state") == "AWAITING_CONFIRMATION":
            is_affirmative = any(kw in lower_msg for kw in ["haan", "yes", "confirm", "theek hai", "ok", "kardo", "krdo", "done", "jee"])
            is_negative = any(kw in lower_msg for kw in ["no", "nahi", "cancel", "mat karo", "stop"])

            if is_affirmative:
                item_snap = pending["selected_item"]
                new_price = pending["proposed_price"]
                item_id = uuid.UUID(item_snap["id"])
                old_price = item_snap["price"]

                await catalog_repo.update_item_price(session, item_id, new_price)
                await price_log_repo.log_price_change(
                    session=session,
                    tenant_id=tenant_id,
                    catalog_item_id=item_id,
                    item_name=item_snap["name"],
                    old_price=old_price,
                    new_price=new_price,
                    changed_by_phone=owner_phone,
                    metadata_json=item_snap.get("metadata_json", {}),
                )

                if on_cache_invalidate:
                    try:
                        on_cache_invalidate(str(tenant_id))
                    except Exception:
                        pass

                self.clear_pending_state(owner_phone)
                origin_str = f" ({item_snap['origin']})" if item_snap.get("origin") else ""
                return {
                    "reply": f"Updated bhai. {item_snap['name']}{origin_str} ab PKR {int(new_price):,} ho gaya sheet mein. AI ab quote karna shuru kar dega.",
                    "is_price_updated": True,
                }

            elif is_negative:
                self.clear_pending_state(owner_phone)
                return {"reply": "Price update cancelled."}
            else:
                return {"reply": "Please reply 'haan' / 'yes' to confirm or 'cancel' to abort."}

        # 3. New price intent
        intent = await self.extract_price_intent(message_text)
        if not intent:
            return None

        product_name = intent["product_name"]
        new_price = float(intent["new_price"])
        origin = intent.get("origin")

        matches = await self.match_catalog_items(session, tenant_id, product_name, origin=origin)
        if not matches:
            return {"reply": f"Catalog mein '{product_name}' nahi mila. Please product ka sahi model batayein."}

        if len(matches) > 1:
            match_snaps = [self._snapshot_item(m) for m in matches]
            self._pending_updates[owner_phone] = {
                "state": "AWAITING_DISAMBIGUATION",
                "tenant_id": tenant_id,
                "proposed_price": new_price,
                "matches": match_snaps,
            }

            lines = [f"Found {len(matches)} matches for '{product_name}':"]
            for idx, m in enumerate(match_snaps, 1):
                org = f"{m['origin']} — " if m.get("origin") else ""
                lines.append(f"({idx}) {org}currently PKR {int(m['price']):,}")
            lines.append(f"Which one? Reply 1 to {len(matches)}.")
            return {"reply": "\n".join(lines)}

        single_item = self._snapshot_item(matches[0])
        self._pending_updates[owner_phone] = {
            "state": "AWAITING_CONFIRMATION",
            "tenant_id": tenant_id,
            "proposed_price": new_price,
            "selected_item": single_item,
        }

        origin_str = f" ({single_item['origin']})" if single_item.get("origin") else ""
        old_p_str = f"PKR {int(single_item['price']):,}"
        new_p_str = f"PKR {int(new_price):,}"

        return {
            "reply": f"Confirm: update {single_item['name']}{origin_str}, from {old_p_str} to {new_p_str}?\n\nReply 'haan' / 'yes' to confirm or 'cancel'."
        }
