import asyncio
from contextlib import asynccontextmanager

import asyncpg
from decouple import UndefinedValueError, config

from src.core.logger import Logger
from src.core.response import CustomError


class Database:
    def __init__(self, database_url=None):
        self.database_url = database_url or self._get_database_url()
        self.logger = Logger("db").get_logger()

    def _get_database_url(self):
        try:
            return config("DATABASE_URL")
        except UndefinedValueError:
            db_user = config("DB_USER")
            db_password = config("DB_PASSWORD")
            db_name = config("DB_NAME")
            db_host = config("DB_HOST")
            db_port = config("DB_PORT")

            password_part = f":{db_password}" if db_password else ""
            return (
                f"postgresql://{db_user}{password_part}@{db_host}:"
                f"{db_port}/{db_name}"
            )

    async def initialize(self, retries=10, delay=3):
        """Initialize the connection pool on startup with retry logic."""
        for attempt in range(1, retries + 1):
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=self.database_url,
                    min_size=5,
                    max_size=20,
                    timeout=30,
                )
                self.logger.info("Database pool initialized.")
                return
            except asyncpg.CannotConnectNowError as e:
                self.logger.warning(
                    f"[Attempt {attempt}/{retries}]"
                    f"Database not ready yet: {e}"
                )
            except asyncpg.PostgresError as e:
                self.logger.error(
                    f"[Attempt {attempt}/{retries}] Failed to connect: {e}"
                )
            except Exception as e:
                self.logger.error(
                    f"[Attempt {attempt}/{retries}] Unexpected error: {e}"
                )
            await asyncio.sleep(delay)

        self.logger.critical("Database initialization failed after retries.")
        raise RuntimeError(
            "Failed to initialize database connection pool after retries."
        )

    async def close(self):
        """Close the connection pool on shutdown."""
        if self.pool:
            await self.pool.close()
            self.logger.info("Database pool closed.")

    @asynccontextmanager
    async def _get_connection(self):
        """Acquire a connection from the pool."""
        connection = None
        try:
            connection = await self.pool.acquire()
            yield connection
        except asyncpg.PostgresError as e:
            self.logger.error(f"Connection error: {e}")
            yield None
        finally:
            if connection:
                await self.pool.release(connection)

    async def commit(self, query, params=None):
        """Execute a query that modifies data (INSERT, UPDATE, DELETE)."""
        async with self._get_connection() as connection:
            if connection is None:
                self.logger.error("Failed to get a database connection.")
                return None

            try:
                if "RETURNING" in query.upper():
                    result = (
                        await connection.fetchrow(query, *params)
                        if params
                        else await connection.fetchrow(query)
                    )
                    return dict(result) if result else None
                (
                    await connection.execute(query, *params)
                    if params
                    else await connection.execute(query)
                )
                return None
            except asyncpg.PostgresError as e:
                self.logger.error(f"Commit error: {e}")
                raise CustomError(f"Database error: {e}", 500)

    async def select(self, query, params=None, format=True):
        """Execute a SELECT query and return results."""
        async with self._get_connection() as connection:
            if connection is None:
                self.logger.error("Failed to get a database connection.")
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
                self.logger.error(f"Select error: {e}")
                raise CustomError(f"Database error: {e}", 500)

    @asynccontextmanager
    async def transaction(self):
        """Provide a transactional scope using asyncpg."""
        async with self._get_connection() as connection:
            if connection is None:
                raise CustomError("Failed to acquire DB connection", 500)

            transaction = connection.transaction()
            await transaction.start()
            try:
                yield
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                raise e
