from db import get_connection


def main() -> None:
    query = "SELECT current_database(), current_user, inet_server_port();"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            database, user, port = cur.fetchone()

    print(f"Banco: {database}")
    print(f"Usuario: {user}")
    print(f"Porta: {port}")


if __name__ == "__main__":
    main()
