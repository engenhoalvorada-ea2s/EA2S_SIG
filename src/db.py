import os

import psycopg2
from dotenv import load_dotenv


REQUIRED_ENV_VARS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


def _get_required_env() -> dict[str, str]:
    load_dotenv()

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(
            f"Variaveis obrigatorias ausentes no .env: {missing_vars}. "
            "Copie .env.example para .env e preencha os valores."
        )

    return {name: os.environ[name] for name in REQUIRED_ENV_VARS}


def get_connection():
    """Retorna uma conexao psycopg2 com o PostgreSQL/PostGIS."""
    env = _get_required_env()

    return psycopg2.connect(
        host=env["DB_HOST"],
        port=env["DB_PORT"],
        dbname=env["DB_NAME"],
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
    )
