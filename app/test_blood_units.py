from db import get_connection


def test_blood_units():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        unit_id,
                        component,
                        blood_group,
                        status,
                        expiry_date
                    FROM blood_unit
                    ORDER BY unit_id;
                """)

                units = cursor.fetchall()

                print("\nBLOODLINK INVENTORY")
                print("-" * 65)

                if not units:
                    print("No blood units found.")
                    return

                for unit in units:
                    print(
                        f"Unit ID: {unit[0]} | "
                        f"Component: {unit[1]} | "
                        f"Blood Group: {unit[2]} | "
                        f"Status: {unit[3]} | "
                        f"Expiry: {unit[4]}"
                    )

                print("-" * 65)
                print(f"Total blood units: {len(units)}")

    except Exception as error:
        print("Failed to retrieve blood units.")
        print("Error:", error)


if __name__ == "__main__":
    test_blood_units()