from contextlib import asynccontextmanager

import asyncpg
from decouple import UndefinedValueError, config

from src.core.error_handler import CustomError
from src.core.logger import Logger

env = config("ENV", default="prod")
is_prod = env == "prod"


class Database:
    def __init__(self, database_url=None):
        self.database_url = database_url or self._get_database_url()

    def _get_database_url(self):
        try:
            return config("DATABASE_URL")
        except UndefinedValueError:
            db_user = config("DB_USER")
            db_password = config("DB_PASSWORD")
            db_name = config("DB_NAME")
            db_host = config("DB_HOST") if is_prod else "localhost"
            db_port = config("DB_PORT") if is_prod else 5431

            password_part = f":{db_password}" if db_password else ""
            return (
                f"postgresql://{db_user}{password_part}@{db_host}:"
                f"{db_port}/{db_name}"
            )

    async def initialize(self):
        """Initialize the connection pool on startup."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=5,
                max_size=20,
                timeout=30,
            )
            Logger("db").get_logger().info("Database pool initialized.")
        except asyncpg.PostgresError as e:
            Logger("db").get_logger().error(f"Failed to initialize pool: {e}")
            raise

    async def close(self):
        """Close the connection pool on shutdown."""
        if self.pool:
            await self.pool.close()
            Logger("db").get_logger().info("Database pool closed.")

    @asynccontextmanager
    async def _get_connection(self):
        """Acquire a connection from the pool."""
        connection = None
        try:
            connection = await self.pool.acquire()
            yield connection
        except asyncpg.PostgresError as e:
            print(f"Connection error: {e}")
            yield None
        finally:
            if connection:
                await self.pool.release(connection)

    async def commit(self, query, params=None):
        """Execute a query that modifies data (INSERT, UPDATE, DELETE)."""
        async with self._get_connection() as connection:
            if connection is None:
                print("Failed to get a database connection.")
                return None

            try:
                if "RETURNING" in query.upper():
                    result = (
                        await connection.fetchrow(query, *params)
                        if params
                        else await connection.fetchrow(query)
                    )
                    return result[0] if result else None
                (
                    await connection.execute(query, *params)
                    if params
                    else await connection.execute(query)
                )
                return None
            except asyncpg.PostgresError as e:
                Logger("db").get_logger().error(f"Commit error: {e}")
                raise CustomError(f"Database error: {e}", 500)

    async def select(self, query, params=None, format=True):
        """Execute a SELECT query and return results."""
        async with self._get_connection() as connection:
            if connection is None:
                print("Failed to get a database connection.")
                return False

            try:
                records = (
                    await connection.fetch(query, *params)
                    if params
                    else await connection.fetch(query)
                )
                col_names = records[0].keys() if records else []

                if format:
                    return [dict(record) for record in records]
                return (col_names, [tuple(record) for record in records])
            except asyncpg.PostgresError as e:
                Logger("db").get_logger().error(f"Select error: {e}")
                raise CustomError(f"Database error: {e}", 500)
