import os
import sys
import uuid
import asyncio
import csv
from typing import List, Dict, Any

# Ensure backend root is on sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openpyxl
from sqlalchemy import select, delete, text
from app.db.session import AsyncSessionLocal
from app.models.database import Tenant, CatalogItem
from app.api.gateway_bridge import invalidate_catalog_cache


EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Haider Arms Data.xlsx")
CSV_PATH = os.path.join(os.path.dirname(__file__), "haider_arms_catalog.csv")
TARGET_OWNER_PHONE = "+923140922056"

# Deterministic exact mappings for Haider Arms catalog product images
EXACT_IMAGE_MAP = {
    # Pistols
    "Glock 19 Gen 5": ["/static/catalog_images/glock_19_gen_5_austria.jpg", "/static/catalog_images/glock_19_gen_5_usa.jpg"],
    "Glock 19X": ["/static/catalog_images/glock_19x_austria.jpg", "/static/catalog_images/glock_19x_usa.jpg"],
    "Glock 19X V MOS": ["/static/catalog_images/glock_19x_v_mos.jpg"],
    "Glock 17 Gen 5": ["/static/catalog_images/glock_17_gen_5_austria.jpg", "/static/catalog_images/glock_17_gen_5_usa.jpg"],
    "Glock 26 Gen 5": ["/static/catalog_images/glock_26_gen_5_usa.jpg"],
    "Glock 45 Gen 5": ["/static/catalog_images/glock_45_gen_5_usa.jpg"],
    "Taurus G3": ["/static/catalog_images/taurus_g3.jpg"],
    "Taurus G3C": ["/static/catalog_images/taurus_g3c.jpg"],
    "Taurus G3 Tactical": ["/static/catalog_images/taurus_g3_tactical.jpg"],
    "Taurus G3C Tactical": ["/static/catalog_images/taurus_g3c.jpg"],
    "Taurus GX4": ["/static/catalog_images/taurus_gx4.jpg"],
    "Taurus GX4 XL": ["/static/catalog_images/taurus_gx4.jpg"],
    "Taurus PT92 AFS Black": ["/static/catalog_images/taurus_pt92_afs_black.jpg"],
    "Taurus PT92 AFS Silver": ["/static/catalog_images/taurus_pt92_afs_silver.jpg"],
    "Taurus PT92 AFS Special Edition": ["/static/catalog_images/taurus_pt92_afs_black.jpg", "/static/catalog_images/taurus_pt92_afs_silver.jpg"],
    "Taurus PT 1911": ["/static/catalog_images/taurus_pt_1911.jpg"],
    "Canik TP9 Sub Elite": ["/static/catalog_images/canik_tp9_sub_elite.jpg"],
    "Canik TP9 SFX": ["/static/catalog_images/canik_tp9_sfx_rival.jpg"],
    "Canik TP9 SFX Rival": ["/static/catalog_images/canik_tp9_sfx_rival.jpg"],
    "Canik TP9 Elite Combat": ["/static/catalog_images/canik_tp9_elite_combat.jpg"],
    "Canik Mete MC9": ["/static/catalog_images/canik_mete_mc9.jpg"],
    "Canik Mete SFX": ["/static/catalog_images/canik_mete_sfx.jpg"],
    "Canik MC9 LS": ["/static/catalog_images/canik_mc9_ls.jpg"],
    "Canik MC9 FDE": ["/static/catalog_images/canik_mc9_fde.jpg"],
    "Canik TTI Combat": ["/static/catalog_images/canik_tti_combat.jpg"],
    "Beretta 92FS Italy Black": ["/static/catalog_images/beretta_92fs_italy_black.jpg"],
    "Beretta 92FS Italy Inox": ["/static/catalog_images/beretta_92fs_italy_inox.jpg"],
    "Beretta M9A4": ["/static/catalog_images/beretta_m9a4.jpg"],
    "Beretta APX Compact": ["/static/catalog_images/beretta_apx_compact.jpg"],
    "CZ P10C": ["/static/catalog_images/cz_p10c.jpg"],
    "CZ Shadow 2 Orange": ["/static/catalog_images/cz_shadow_2_orange.jpg"],
    "CZ Shadow TS 2 Bronze": ["/static/catalog_images/cz_shadow_ts_2_bronze.jpg"],
    "Sig Sauer P320 M18": ["/static/catalog_images/sig_sauer_p320_m18.jpg"],
    "SIG P365": ["/static/catalog_images/sig_sauer_sig_p365.jpg"],
    "Ruger 5.7": ["/static/catalog_images/ruger_5_7.jpg"],
    "Agaoglu FXS 9": ["/static/catalog_images/agaoglu_fxs_9.jpg"],
    "Derya DY9": ["/static/catalog_images/derya_dy9.jpg"],
    "BRG9 Elite": ["/static/catalog_images/brg9_elite.jpg"],
    "Girsan Beretta MC9": ["/static/catalog_images/girsan_beretta_mc9.jpg"],
    "Girsan MC 1911": ["/static/catalog_images/girsan_mc_1911.jpg"],
    "Stoeger STR9": ["/static/catalog_images/stoeger_str9.jpg"],
    "Baikal Makarov 442": ["/static/catalog_images/baikal_makarov_442.jpg"],
    "Norinco NP-7": ["/static/catalog_images/norinco_np_7.jpg"],
    "Norinco 30 Bore": ["/static/catalog_images/norinco_30_bore.jpg"],
    "Norinco PX3": ["/static/catalog_images/norinco_px3.jpg"],
    "HS9": ["/static/catalog_images/hs_produkt_hs9.jpg"],
    "HS9 Subcompact": ["/static/catalog_images/hs_produkt_hs9_subcompact.jpg"],
    "HK SFP9": ["/static/catalog_images/heckler_koch_hk_sfp9.jpg"],
    "HK P30L": ["/static/catalog_images/heckler_koch_hk_p30l.jpg"],
    "HK SFP9 Match": ["/static/catalog_images/heckler_koch_hk_sfp9.jpg"],
    "Desert Eagle .44 Magnum": ["/static/catalog_images/magnum_research_desert_eagle_44_magnum.jpg"],
    "Desert Eagle Tiger Stripe .50 AE": ["/static/catalog_images/magnum_research_desert_eagle_tiger_stripe_50_ae.jpg"],
    "Smith & Wesson 1911 Performance Center": ["/static/catalog_images/smith_wesson_1911_performance_center.jpg"],
    "Kimber Rapide 1911": ["/static/catalog_images/kimber_rapide_1911.jpg"],
    "Zigana PX9 Gen 3": ["/static/catalog_images/zigana_px9_gen_3.jpg"],
    "Zig 14": ["/static/catalog_images/zigana_zig_14.jpg"],
    "Zig 14 Sports Black": ["/static/catalog_images/zigana_zig_14_sports_black.jpg"],
    "Zigana Sports Black": ["/static/catalog_images/zigana_zig_14_sports_black.jpg"],
    "Zig P9": ["/static/catalog_images/zigana_zig_p9.jpg"],
    "Kral KR9": ["/static/catalog_images/kral_kr9.jpg"],
    "Kral KR19": ["/static/catalog_images/kral_kr19.jpg"],
    "Ermox Fire": ["/static/catalog_images/ermox_fire.jpg"],
    "Akdas SA-9": ["/static/catalog_images/akdas_sa_9.jpg"],

    # Rifles
    "Colt M4": ["/static/catalog_images/colt_m4.jpg"],
    "Anderson M4": ["/static/catalog_images/anderson_manufacturing_anderson_m4.jpg"],
    "Diamondback DB10 .308 Win": ["/static/catalog_images/diamondback_db10_308_win_od_green.jpg"],
    "Sig Sauer M400": ["/static/catalog_images/sig_sauer_m400.jpg"],
    "Sig Sauer MPX": ["/static/catalog_images/sig_sauer_mpx.jpg"],
    "Sig Sauer PMPX": ["/static/catalog_images/sig_sauer_pmpx.jpg"],
    "CZ Scorpion": ["/static/catalog_images/cz_scorpion.jpg"],
    "Keltec RDB Bullpup": ["/static/catalog_images/kel_tec_keltec_rdb_bullpup.jpg"],
    "Saiga MK": ["/static/catalog_images/saiga_mk.jpg"],
    "Saiga A-308-1": ["/static/catalog_images/saiga_a_308_1.jpg"],
    "Vepr Molot Krenkove": ["/static/catalog_images/molot_vepr_molot_krenkove.jpg"],
    "Taurus T4": ["/static/catalog_images/taurus_t4.jpg"],
    "Utas Defense AR10": ["/static/catalog_images/utas_defense_ar10.jpg"],
    "Utas Defense 9mm": ["/static/catalog_images/utas_defense_9mm.jpg"],
    "MP5 POF WAH": ["/static/catalog_images/pof_mp5_pof_wah.jpg"],
    "Scar 17 .308": ["/static/catalog_images/fn_herstal_scar_17_308.jpg"],
    "Diamondback DB15": ["/static/catalog_images/diamondback_db15.jpg"],
    "Akdas 223": ["/static/catalog_images/akdas_223.jpg"],
    "Huglu Tactical Bolt Action": ["/static/catalog_images/huglu_tactical_bolt_action.jpg"],

    # Shotguns
    "MKA": ["/static/catalog_images/mka.jpg"],
    "Kral XPS": ["/static/catalog_images/kral_xps.jpg"],
    "Kral XPS Bullpup": ["/static/catalog_images/kral_xps_bullpup.jpg"],
    "Saiga 12 Repeater": ["/static/catalog_images/saiga_12_repeater.jpg"],
    "Bellini Magnum": ["/static/catalog_images/bellini_magnum.jpg"],
    "Kral Cara Cara Over/Under": ["/static/catalog_images/kral_cara_cara_over_under.jpg"],
    "ERMOX XP Pro Series": ["/static/catalog_images/ermox_xp_pro_series.jpg"],
}


def export_excel_to_csv() -> List[Dict[str, Any]]:
    """Exports and parses all rows from Haider Arms Data.xlsx."""
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"Excel file not found at: {EXCEL_PATH}")

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    sheet = wb["Sheet1"]
    rows = list(sheet.iter_rows(values_only=True))

    products = []
    # Row 3 is header: Model Name, Category, Brand, Origin, Caliber, Capacity, Action, Price (PKR)
    for idx, r in enumerate(rows[4:]):
        name = r[0]
        if not name or not str(name).strip() or str(name).startswith("HAIDER"):
            continue

        category = str(r[1]).strip() if r[1] else "General"
        brand = str(r[2]).strip() if r[2] else ""
        origin = str(r[3]).strip() if r[3] else ""
        caliber = str(r[4]).strip() if r[4] else ""
        capacity = r[5]
        action = str(r[6]).strip() if r[6] else ""
        try:
            price = float(r[7]) if r[7] is not None else 0.0
        except Exception:
            price = 0.0

        cap_str = f"{int(capacity)} rds" if isinstance(capacity, (int, float)) else str(capacity or "")
        desc_parts = []
        if brand:
            desc_parts.append(f"Brand: {brand}")
        if origin:
            desc_parts.append(f"Origin: {origin}")
        if caliber:
            desc_parts.append(f"Caliber: {caliber}")
        if cap_str:
            desc_parts.append(f"Capacity: {cap_str}")
        if action:
            desc_parts.append(f"Action: {action}")
        description = " | ".join(desc_parts)

        products.append({
            "name": str(name).strip(),
            "category": category,
            "brand": brand,
            "origin": origin,
            "caliber": caliber,
            "capacity": cap_str,
            "action": action,
            "price": price,
            "description": description,
        })

    # Ensure single genuine Diamondback DB10 is included if missing from master sheet
    if not any("db10" in p["name"].lower() for p in products):
        products.append({
            "name": "Diamondback DB10 .308 Win",
            "category": "Rifle",
            "brand": "Diamondback",
            "origin": "USA",
            "caliber": ".308 Win",
            "capacity": "20 rds",
            "action": "Semi Auto",
            "price": 700000.0,
            "description": "Brand: Diamondback | Origin: USA | Caliber: .308 Win | Capacity: 20 rds | Action: Semi Auto | Genuine USA Import",
        })

    # Also save as CSV for fast reference and syncing
    try:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "name", "category", "brand", "origin", "caliber", "capacity", "action", "price", "description"
            ])
            writer.writeheader()
            writer.writerows(products)
        print(f"Exported {len(products)} firearms to {CSV_PATH}")
    except Exception as e:
        print(f"Notice: Could not write CSV to {CSV_PATH} ({e}), continuing with DB sync...")

    return products


async def sync_catalog():
    products = export_excel_to_csv()
    print(f"Loaded {len(products)} firearms from master dataset.")

    async with AsyncSessionLocal() as session:
        # 1. Locate Tenant
        stmt = select(Tenant).where(
            (Tenant.business_phone.ilike("%3040124445%")) |
            (Tenant.name.ilike("%Haider%"))
        )
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()

        if not tenant:
            print("Haider Arms tenant not found in local DB. Creating tenant...")
            tenant = Tenant(
                name="Haider Arms Official",
                business_phone="+923040124445",
                owner_phone=TARGET_OWNER_PHONE,
                industry="Firearms & Ammunition",
                status="active",
                business_profile={
                    "business_name": "Haider Arms",
                    "city": "Peshawar",
                    "prices_confirmed_today": True,
                },
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        else:
            old_owner = tenant.owner_phone
            tenant.owner_phone = TARGET_OWNER_PHONE
            if not tenant.business_profile:
                tenant.business_profile = {}
            tenant.business_profile["prices_confirmed_today"] = True
            await session.commit()
            print(f"Updated Tenant: {tenant.name} (ID: {tenant.id}) | Owner: {old_owner} -> {tenant.owner_phone}")

        tenant_id = tenant.id

        # Preserve owner-uploaded items (e.g. Tisas variants with inbound photos)
        existing_res = await session.execute(select(CatalogItem).where(CatalogItem.tenant_id == tenant_id))
        existing_items = existing_res.scalars().all()
        preserved_custom = [
            it for it in existing_items
            if any("inbound_" in str(img) for img in (it.images or []))
            and not any(p["name"].lower() == it.name.lower() for p in products)
        ]

        # 2. Clear old base items for this tenant
        del_stmt = delete(CatalogItem).where(CatalogItem.tenant_id == tenant_id)
        del_res = await session.execute(del_stmt)
        print(f"Cleared {del_res.rowcount} old catalog items.")

        # 3. Insert all firearms from master dataset
        inserted = 0
        for p in products:
            item = CatalogItem(
                tenant_id=tenant_id,
                name=p["name"],
                price=p["price"],
                description=p["description"],
                category=p["category"],
                images=EXACT_IMAGE_MAP.get(p["name"], []),
                metadata_json={
                    "brand": p["brand"],
                    "origin": p["origin"],
                    "caliber": p["caliber"],
                    "capacity": p["capacity"],
                    "action": p["action"],
                },
                in_stock=True,
            )
            session.add(item)
            inserted += 1

        # Re-insert preserved owner-uploaded items
        for cit in preserved_custom:
            new_cit = CatalogItem(
                tenant_id=tenant_id,
                name=cit.name,
                price=cit.price,
                description=cit.description,
                category=cit.category,
                images=cit.images,
                metadata_json=cit.metadata_json,
                in_stock=True,
            )
            session.add(new_cit)
            inserted += 1

        await session.commit()
        print(f"Successfully synced {inserted} firearms to DB for tenant {tenant.name} (including {len(preserved_custom)} preserved custom items)!")

        # 4. Flush cache
        invalidate_catalog_cache(str(tenant_id))
        print("Flushed catalog cache successfully.")


if __name__ == "__main__":
    asyncio.run(sync_catalog())
