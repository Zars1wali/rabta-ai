"""
Resume interrupted Haider Arms bulk catalog import (images + SKU enrichment).

Source of truth: ~/Downloads/haider_arms_final_import.json (114 items, SKUs
HA-PST/HA-RIF/HA-SHG). Matched product photos live in ~/Downloads/ai_images_matched.

Logic:
  1. Stage the 87 referenced product images into backend/app/static/catalog_images/.
  2. Enrich existing catalog rows (matched by name + price) with images + metadata_json.
  3. Delete stale rows that do not correspond to any payload item.
  4. Insert payload items that have no matching row.
  5. Verify: 114 rows, all SKUs present, image/URL consistency.

Dry-run by default; pass --apply to execute.
Idempotent: re-running reports the same steady state and makes no changes.
"""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo
from app.models.database import CatalogItem, Tenant

DOWNLOADS = Path(os.path.expanduser("~")) / "Downloads"
PAYLOAD_PATH = DOWNLOADS / "haider_arms_final_import.json"
MATCHED_DIR = DOWNLOADS / "ai_images_matched"
CATALOG_IMAGES_DIR = (
    Path(__file__).resolve().parent.parent / "app" / "static" / "catalog_images"
)
EXPECTED_COUNT = 114


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_payload():
    data = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    if len(data) != EXPECTED_COUNT:
        raise SystemExit(f"Unexpected payload size: {len(data)} (expected {EXPECTED_COUNT})")
    by_key = {(it["name"].strip(), float(it["price"])): it for it in data}
    if len(by_key) != EXPECTED_COUNT:
        dup = EXPECTED_COUNT - len(by_key)
        raise SystemExit(f"Payload has {dup} duplicate (name, price) keys")
    return data, by_key


def plan_images(payload):
    staged, skipped, failed = [], [], []
    ref_absent = []
    urls_seen = set()
    for it in payload:
        for url in it.get("images") or []:
            if url in urls_seen:
                continue
            urls_seen.add(url)
            fname = os.path.basename(url)
            src = MATCHED_DIR / fname
            dst = CATALOG_IMAGES_DIR / fname
            if not src.exists():
                ref_absent.append(fname)
                continue
            if dst.exists() and sha256(dst) == sha256(src):
                skipped.append(fname)
            else:
                staged.append(fname)
    return staged, skipped, failed, ref_absent


def validate_images(fnames):
    bad = []
    for f in fnames:
        p = CATALOG_IMAGES_DIR / f
        try:
            with Image.open(p) as im:
                im.load()
            if p.stat().st_size <= 0:
                bad.append((f, "zero size"))
        except Exception as e:
            bad.append((f, str(e)))
    return bad


async def load_db_rows(session):
    tenant = await tenant_repo.get_tenant_by_phone(session, "923040124445")
    if not tenant or tenant.name != "Haider Arms Official":
        raise SystemExit("Haider Arms tenant not found")
    rows = (
        await session.execute(
            select(CatalogItem).where(CatalogItem.tenant_id == tenant.id)
        )
    ).scalars().all()
    return tenant, rows


def diff_db(rows, payload_by_key):
    keyed = {}
    for r in rows:
        k = (r.name.strip(), float(r.price))
        if k in keyed:
            raise SystemExit(f"Duplicate DB key: {k}")
        keyed[k] = r
    matched = [r for k, r in keyed.items() if k in payload_by_key]
    stale = [r for k, r in keyed.items() if k not in payload_by_key]
    missing = [
        it for it in payload_by_key.values() if (it["name"].strip(), float(it["price"])) not in keyed
    ]
    return matched, stale, missing


async def main(apply: bool):
    CATALOG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    payload, payload_by_key = load_payload()

    async with AsyncSessionLocal() as session:
        tenant, rows = await load_db_rows(session)
        matched, stale, missing = diff_db(rows, payload_by_key)

        print("=" * 78)
        print(f"HAIDER ARMS IMPORT RESUME  | tenant={tenant.name} ({tenant.id})")
        print(f"Payload items: {len(payload)} | DB rows: {len(rows)}")
        print(f"Matched rows (enrich in place):       {len(matched)}")
        print(f"Stale rows not in payload (delete):   {len(stale)}")
        for r in stale:
            print(f"    - {r.name} | {float(r.price):,.0f} | id={r.id}")
        print(f"Payload items missing a row (insert): {len(missing)}")
        for it in missing:
            print(f"    + {it['metadata_json']['sku']} | {it['name']} | {float(it['price']):,.0f} | images={len(it.get('images') or [])}")
        with_img = sum(1 for it in payload if it.get("images"))
        print(f"Payload items with images: {with_img} | without: {len(payload) - with_img}")

        staged, skipped, failed, ref_absent = plan_images(payload)
        print(f"\nImage staging (target: {CATALOG_IMAGES_DIR}):")
        print(f"    to copy: {len(staged)} | already present & identical: {len(skipped)}")
        print(f"    referenced but missing on disk: {len(ref_absent)}")
        for f in ref_absent:
            print(f"        MISSING-SRC: {f}")

        if not apply:
            print("\nDRY RUN — no changes made. Re-run with --apply to execute.")
            return

        print("\n-- Applying --")
        for f in staged:
            src = MATCHED_DIR / f
            dst = CATALOG_IMAGES_DIR / f
            shutil.copyfile(src, dst)
            print(f"    copied  {f} -> {dst.name}")
        bad = validate_images(staged + skipped)
        if bad:
            raise SystemExit(f"Image validation failed: {bad}")
        print(f"    images validated (PIL): {len(staged) + len(skipped)} OK")

        for r in stale:
            await session.delete(r)
            print(f"    deleted stale row: {r.name} | {float(r.price):,.0f}")
        if stale:
            await session.flush()

        for r in matched:
            it = payload_by_key[(r.name.strip(), float(r.price))]
            r.images = list(it.get("images") or [])
            r.metadata_json = dict(it["metadata_json"])
            print(
                f"    enriched {r.id} | {it['metadata_json']['sku']} | {it['name']} | images={len(r.images)}"
            )

        for it in missing:
            new_row = CatalogItem(
                tenant_id=tenant.id,
                name=it["name"].strip(),
                price=it["price"],
                description=it.get("description"),
                category=it.get("category"),
                images=list(it.get("images") or []),
                metadata_json=dict(it["metadata_json"]),
                in_stock=True,
            )
            session.add(new_row)
            print(f"    inserted {it['metadata_json']['sku']} | {it['name']} | {float(it['price']):,.0f} | images={len(new_row.images)}")

        await session.commit()

        await verify(tenant)


async def verify(tenant: Tenant):
    print("\n-- Verification --")
    async with AsyncSessionLocal() as session:
        all_rows = (
            await session.execute(
                select(CatalogItem).where(CatalogItem.tenant_id == tenant.id)
            )
        ).scalars().all()
        print(f"DB rows for tenant: {len(all_rows)} (expected {EXPECTED_COUNT})")
        no_sku = [r for r in all_rows if not (r.metadata_json or {}).get("sku")]
        with_img = [r for r in all_rows if r.images]
        print(f"rows without SKU: {len(no_sku)} | rows with >=1 image: {len(with_img)}")
        sku_fams = Counter((r.metadata_json or {}).get("sku", "").split("-")[1] for r in all_rows if (r.metadata_json or {}).get("sku"))
        print(f"SKU families: {dict(sku_fams)}")

        img_files = set(os.listdir(CATALOG_IMAGES_DIR))
        print(f"files in catalog_images: {len(img_files)}")
        missing_files = []
        for r in with_img:
            for u in r.images:
                f = os.path.basename(u)
                if f not in img_files:
                    missing_files.append((r.name, u))
        print(f"rows whose image URL has no file: {len(missing_files)}")
        for name, u in missing_files[:10]:
            print(f"    BROKEN-URL: {name} | {u}")

        import random
        sample = random.sample(all_rows, min(3, len(all_rows)))
        print("\nSpot-check (random):")
        for r in sorted(sample, key=lambda x: x.name):
            meta = r.metadata_json or {}
            imgs = r.images or []
            file_ok = "n/a"
            if imgs:
                p = CATALOG_IMAGES_DIR / os.path.basename(imgs[0])
                file_ok = "OK" if p.exists() and p.stat().st_size > 0 else "MISSING"
            print(
                f"    {meta.get('sku')} | {r.name} | {float(r.price):,.0f} | images={len(imgs)} ({imgs[0] if imgs else '[]'}) | file={file_ok}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Haider Arms catalog import.")
    parser.add_argument("--apply", action="store_true", help="Execute writes (default is dry-run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))