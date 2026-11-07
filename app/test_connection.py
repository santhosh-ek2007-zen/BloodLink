from db import get_connection


def test_connection():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), version();"
                )

                result = cursor.fetchone()

                if result is None:
                    print("No results retured from database.")
                    return
                
                print("Database connection successful!")
                print("Database name:", result[0])
                print("PostgreSQL version:", result[1])

    except Exception as error:
        print("Database connection failed!")
        print("Error:", error)


if __name__ == "__main__":
    test_connection()