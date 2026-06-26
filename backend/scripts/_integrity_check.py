import os, asyncio
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]
    products = await db["products"].count_documents({})
    prices = await db["prices"].count_documents({})
    product_names = [d["normalized_name"] async for d in db["products"].find({}, {"normalized_name": 1})]
    orphan_prices = await db["prices"].count_documents({"product_id": {"$nin": product_names}})
    print(f"products: {products}")
    print(f"prices: {prices}")
    print(f"prices sem produto correspondente (deve ser 0): {orphan_prices}")
    client.close()

asyncio.run(check())
