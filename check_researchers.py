import asyncio
import json
from app.database.supabase_client import get_supabase_client

async def get_researchers():
    client = await get_supabase_client()
    response = await client.table('researchers').select('*').order('created_at', desc=True).limit(2).execute()
    print(json.dumps(response.data, indent=2))

if __name__ == "__main__":
    asyncio.run(get_researchers()) 