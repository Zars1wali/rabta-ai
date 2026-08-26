import json
import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Whitelist Management"])

APPROVED_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "whatsapp-gateway", "approved_numbers.json")


class WhitelistRequest(BaseModel):
    phone: str = Field(..., example="923001234567")
    business_name: str = Field(..., example="Al-Karam Fabrics")
    plan: Optional[str] = Field("PAID_PILOT", example="PAID_PILOT")


def load_approved_list():
    if os.path.exists(APPROVED_FILE):
        try:
            with open(APPROVED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"approved_numbers": []}


def save_approved_list(data):
    with open(APPROVED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@router.get("/whitelist")
async def get_whitelisted_numbers():
    """Returns all currently approved Pakistani business numbers."""
    return load_approved_list()


@router.post("/whitelist/add")
async def add_whitelisted_number(payload: WhitelistRequest):
    """Admin endpoint to approve a business phone number so they can connect."""
    clean_phone = payload.phone.replace("+", "").replace(" ", "").replace("-", "").strip()
    data = load_approved_list()

    # Check if already approved
    for item in data["approved_numbers"]:
        if item["phone"] == clean_phone:
            item["status"] = "APPROVED"
            item["business_name"] = payload.business_name
            save_approved_list(data)
            return {"status": "success", "message": f"Number +{clean_phone} updated to APPROVED."}

    # Add new approved number
    data["approved_numbers"].append({
        "phone": clean_phone,
        "business_name": payload.business_name,
        "status": "APPROVED",
        "plan": payload.plan,
    })
    save_approved_list(data)

    logger.info("Admin approved phone number for Rabta AI: +%s (%s)", clean_phone, payload.business_name)
    return {
        "status": "success",
        "message": f"Phone +{clean_phone} is now APPROVED and authorized to link WhatsApp!",
        "total_approved": len(data["approved_numbers"])
    }


@router.post("/whitelist/revoke")
async def revoke_number(phone: str):
    """Instantly blocks and revokes access for a number."""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").strip()
    data = load_approved_list()

    for item in data["approved_numbers"]:
        if item["phone"] == clean_phone:
            item["status"] = "REVOKED"
            save_approved_list(data)
            return {"status": "success", "message": f"Access REVOKED for +{clean_phone}. AI will stop answering."}

    raise HTTPException(status_code=404, detail="Phone number not found in whitelist")
