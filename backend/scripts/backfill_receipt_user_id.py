"""
Atribui os cupons legados (sem user_id) a uma conta existente.

Contexto: antes da feature de login multi-usuário, os cupons em 'receipts' não
tinham user_id. Depois dela, cupons sem user_id ficam órfãos — invisíveis no
histórico de qualquer usuário e impossíveis de re-salvar (409 permanente). Este
script adota esses cupons órfãos, associando-os ao email informado.

Segurança:
    - Só toca documentos SEM user_id (filtro {"user_id": {"$exists": False}}).
      Cupons que já pertencem a alguém nunca são reatribuídos.
    - Exige que o email alvo já exista na coleção 'users' (crie a conta primeiro
      via signup no app) — evita atribuir dados a uma conta inexistente.

Uso:
    cd backend/
    python scripts/backfill_receipt_user_id.py <email>            # aplica
    python scripts/backfill_receipt_user_id.py <email> --dry-run  # simula
"""
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # deve vir antes de qualquer os.getenv no nível de módulo

from motor.motor_asyncio import AsyncIOMotorClient

# Só cupons sem user_id — nunca reatribui os que já têm dono.
ORPHAN_FILTER = {"user_id": {"$exists": False}}


async def main(email: str, dry_run: bool) -> None:
    email = email.strip().lower()  # mesmo normalize que os endpoints de auth fazem
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]
    prefix = "[DRY-RUN] " if dry_run else ""

    # A conta alvo precisa existir — não atribui cupons a um email que ninguém cadastrou.
    user = await db["users"].find_one({"email": email})
    if not user:
        print(f"ERRO: nenhum usuário com email {email!r} encontrado na coleção 'users'.")
        print("Crie a conta primeiro (signup no app) e rode o script de novo.")
        client.close()
        sys.exit(1)

    orphan_count = await db["receipts"].count_documents(ORPHAN_FILTER)
    print(f"{orphan_count} cupom(ns) órfão(s) (sem user_id) encontrado(s).")

    if orphan_count == 0:
        print("Nada a fazer.")
        client.close()
        return

    if dry_run:
        print(f"{prefix}Atribuiria {orphan_count} cupom(ns) a {email!r}.")
    else:
        result = await db["receipts"].update_many(ORPHAN_FILTER, {"$set": {"user_id": email}})
        print(f"{result.modified_count} cupom(ns) atribuído(s) a {email!r}.")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adota cupons legados (sem user_id) para uma conta.")
    parser.add_argument("email", help="Email da conta que vai adotar os cupons órfãos (precisa já existir)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem alterar o banco")
    args = parser.parse_args()
    asyncio.run(main(email=args.email, dry_run=args.dry_run))
