from app.db import get_connection

try:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            print("Connected database:", cursor.fetchone()[0])

    print("Neon connection successful!")

except Exception as error:
    print("Connection failed:", error)