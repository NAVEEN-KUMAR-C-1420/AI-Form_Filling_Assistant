import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:Akil_1265@localhost:2600/form_assistant')
    
    # Check existing enum values
    result = await conn.fetch("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'entitytype') ORDER BY enumsortorder")
    print("Current entitytype enum values:")
    for r in result:
        print(f"  - {r['enumlabel']}")
    
    # Add new enum values for driving license
    new_values = [
        'DRIVING_LICENSE_NUMBER',
        'BLOOD_GROUP',
        'ORGAN_DONOR',
        'VALIDITY_DATE',
        'ISSUE_DATE'
    ]
    
    for val in new_values:
        try:
            await conn.execute(f"ALTER TYPE entitytype ADD VALUE IF NOT EXISTS '{val}'")
            print(f"Added {val}")
        except Exception as e:
            print(f"{val} error: {e}")
    
    # Check documenttype enum and add driving_license
    result = await conn.fetch("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'documenttype') ORDER BY enumsortorder")
    print("\nCurrent documenttype enum values:")
    for r in result:
        print(f"  - {r['enumlabel']}")
    
    try:
        await conn.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'DRIVING_LICENSE'")
        print("Added DRIVING_LICENSE to documenttype")
    except Exception as e:
        print(f"DRIVING_LICENSE documenttype error: {e}")
    
    # Check again
    result = await conn.fetch("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'entitytype') ORDER BY enumsortorder")
    print("\nUpdated entitytype enum values:")
    for r in result:
        print(f"  - {r['enumlabel']}")
    
    await conn.close()

asyncio.run(main())
