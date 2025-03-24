import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Get Supabase credentials from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

async def fix_highlight_type_constraint():
    """
    Fix the highlight_type constraint in the messages table to allow 'summary' and 'explanation' values.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        return
    
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    try:
        # First, check what the current constraint is
        print("Checking current table schema...")
        
        # Execute SQL to modify the constraint
        print("Modifying highlight_type constraint...")
        
        # For Supabase, we need to use the PostgreSQL RPC functionality
        # First try to see if we can execute raw SQL
        try:
            # We need to use the rpc function for this
            response = supabase.rpc(
                "exec_sql", 
                {
                    "sql_query": """
                    ALTER TABLE messages 
                    DROP CONSTRAINT IF EXISTS messages_highlight_type_check;
                    
                    ALTER TABLE messages 
                    ADD CONSTRAINT messages_highlight_type_check 
                    CHECK (highlight_type IN ('summary', 'explanation') OR highlight_type IS NULL);
                    """
                }
            ).execute()
            
            print("Success! The constraint has been updated.")
            print(response)
            
        except Exception as e:
            print(f"Error executing RPC: {str(e)}")
            print("Alternative approach: You need to run this SQL in the Supabase SQL Editor:")
            print("""
            ALTER TABLE messages 
            DROP CONSTRAINT IF EXISTS messages_highlight_type_check;
            
            ALTER TABLE messages 
            ADD CONSTRAINT messages_highlight_type_check 
            CHECK (highlight_type IN ('summary', 'explanation') OR highlight_type IS NULL);
            """)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Please run this SQL in the Supabase SQL Editor:")
        print("""
        ALTER TABLE messages 
        DROP CONSTRAINT IF EXISTS messages_highlight_type_check;
        
        ALTER TABLE messages 
        ADD CONSTRAINT messages_highlight_type_check 
        CHECK (highlight_type IN ('summary', 'explanation') OR highlight_type IS NULL);
        """)

if __name__ == "__main__":
    asyncio.run(fix_highlight_type_constraint()) 