"""
Re-normaliza todos os produtos no banco com o pipeline completo (pre_process + LLM + canonicalize)
e funde duplicatas detectadas por similaridade.

Fases:
    1. Re-normalizar — mapeia cada original_description → novo product_id
    2. Fundir duplicatas — detecta clusters com similarity >= CANONICAL_THRESHOLD,
       escolhe o nome mais longo como canônico
    3. Relatório — imprime resumo de todas as mudanças

Uso:
    cd backend/
    python scripts/dedup_and_renormalize.py           # aplica as mudanças
    python scripts/dedup_and_renormalize.py --dry-run # simula sem tocar no banco
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.normalizer import normalize_items, CANONICAL_THRESHOLD

load_dotenv()

BATCH = 10  # descrições originais por chamada ao Groq


def _find_clusters(names: list[str]) -> list[list[str]]:
    """Agrupa nomes com similarity >= CANONICAL_THRESHOLD em clusters.

    Usa union-find implícito: cada nome entra no primeiro cluster ao qual é similar.
    """
    assigned = [False] * len(names)
    clusters = []
    for i, a in enumerate(names):
        if assigned[i]:
            continue
        cluster = [a]
        assigned[i] = True
        for j in range(i + 1, len(names)):
            if assigned[j]:
                continue
            if SequenceMatcher(None, a.lower(), names[j].lower()).ratio() >= CANONICAL_THRESHOLD:
                cluster.append(names[j])
                assigned[j] = True
        if len(cluster) > 1:
            clusters.append(cluster)
    return clusters


async def main(dry_run: bool) -> None:
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]
    prefix = "[DRY-RUN] " if dry_run else ""

    # ── Fase 1: Re-normalizar ──────────────────────────────────────────────────
    print("=== FASE 1: Re-normalização via pipeline completo ===\n")

    all_prices = await db["prices"].find(
        {}, {"_id": 0, "original_description": 1, "product_id": 1}
    ).to_list(length=None)

    # Mapeia descrição original → product_id atual (primeira ocorrência)
    desc_to_current: dict[str, str] = {}
    for doc in all_prices:
        desc = doc["original_description"]
        if desc not in desc_to_current:
            desc_to_current[desc] = doc["product_id"]

    unique_descs = list(desc_to_current.keys())
    print(f"{len(unique_descs)} descrições originais distintas encontradas.")

    # Carrega produtos existentes como âncoras iniciais
    existing_docs = await db["products"].find(
        {}, {"_id": 0, "normalized_name": 1}
    ).to_list(length=None)
    anchors: list[str] = [d["normalized_name"] for d in existing_docs]

    desc_to_new: dict[str, str] = {}
    for i in range(0, len(unique_descs), BATCH):
        batch = unique_descs[i: i + BATCH]
        normalized = await normalize_items(batch, anchors)
        for desc, new_name in zip(batch, normalized):
            desc_to_new[desc] = new_name
            if new_name not in anchors:
                anchors.append(new_name)

    phase1_changes: list[tuple[str, str, str]] = []  # (desc, old, new)
    for desc, new_name in desc_to_new.items():
        old_name = desc_to_current[desc]
        if old_name == new_name:
            continue
        phase1_changes.append((desc, old_name, new_name))
        print(f"  {prefix}{old_name!r}\n      -> {new_name!r}  (desc: {desc!r})\n")

        if not dry_run:
            await db["prices"].update_many(
                {"original_description": desc},
                {"$set": {"product_id": new_name}},
            )
            now = datetime.now(timezone.utc)
            await db["products"].update_one(
                {"normalized_name": new_name},
                {"$setOnInsert": {"normalized_name": new_name, "created_at": now}},
                upsert=True,
            )
            still_used = await db["prices"].count_documents({"product_id": old_name})
            if not still_used:
                await db["products"].delete_one({"normalized_name": old_name})

    print(f"{len(phase1_changes)} re-normalizações na Fase 1.\n")

    # ── Fase 2: Fundir duplicatas remanescentes ────────────────────────────────
    print("=== FASE 2: Fusão de duplicatas remanescentes ===\n")

    current_products = await db["products"].find(
        {}, {"_id": 0, "normalized_name": 1}
    ).to_list(length=None)
    current_names = [d["normalized_name"] for d in current_products]
    products_before = len(current_names)

    clusters = _find_clusters(current_names)
    phase2_merges: list[tuple[str, list[str]]] = []

    for cluster in clusters:
        canonical = max(cluster, key=len)  # mais longo = mais completo
        others = [n for n in cluster if n != canonical]
        phase2_merges.append((canonical, others))
        print(f"  Cluster canônico: {canonical!r}")
        for other in others:
            print(f"    {prefix}fundindo {other!r} -> {canonical!r}")
            if not dry_run:
                await db["prices"].update_many(
                    {"product_id": other},
                    {"$set": {"product_id": canonical}},
                )
                await db["products"].delete_one({"normalized_name": other})

    if not clusters:
        print("  Nenhuma duplicata encontrada.")

    total_merged = sum(len(o) for _, o in phase2_merges)
    print(f"\n{total_merged} produtos fundidos em {len(clusters)} clusters.\n")

    # ── Fase 3: Relatório ──────────────────────────────────────────────────────
    print("=== RESUMO ===\n")
    products_after = await db["products"].count_documents({}) if not dry_run else "N/A (dry-run)"
    print(f"  Produtos antes da Fase 2 : {products_before}")
    print(f"  Produtos após            : {products_after}")
    print(f"  Re-normalizações (Fase 1): {len(phase1_changes)}")
    print(f"  Fusões (Fase 2)          : {total_merged}")
    if dry_run:
        print("\n  [DRY-RUN] Nenhuma alteração foi feita no banco.")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-normaliza e deduplica produtos no banco.")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem alterar o banco")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
