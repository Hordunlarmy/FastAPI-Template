import asyncio
import contextvars
from contextlib import asynccontextmanager

import asyncpg
from decouple import UndefinedValueError, config
from oguild.logs import Logger
from oguild.response import Error

current_connection = contextvars.ContextVar("current_connection", default=None)


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

    async def initialize(self, retries=20, delay=20):
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
        connection = None
        try:
            connection = await self.pool.acquire()
            yield connection
        finally:
            if connection:
                await self.pool.release(connection)

    async def commit(self, query, params=None):
        """Execute a query that modifies data (INSERT, UPDATE, DELETE)."""
        connection = current_connection.get(None)

        if connection is None:
            async with self._get_connection() as connection:
                if connection is None:
                    self.logger.error("Failed to get a database connection.")
                    return None
                return await self._execute_query(connection, query, params)
        else:
            return await self._execute_query(connection, query, params)

    async def _execute_query(self, connection, query, params=None):
        """Helper to execute a query using the given connection."""
        if "RETURNING" in query.upper():
            result = (
                await connection.fetchrow(query, *params)
                if params
                else await connection.fetchrow(query)
            )
            return dict(result) if result else None
        else:
            if params:
                await connection.execute(query, *params)
            else:
                await connection.execute(query)
            return None

    async def select(self, query, params=None, format=True):
        """Execute a SELECT query and return results."""
        async with self._get_connection() as connection:
            if connection is None:
                self.logger.error("Failed to get a database connection.")
                return False

            records = (
                await connection.fetch(query, *params)
                if params
                else await connection.fetch(query)
            )
            col_names = records[0].keys() if records else []

            if format:
                return [dict(record) for record in records]
            return (col_names, [tuple(record) for record in records])

    @asynccontextmanager
    async def transaction(self):
        """Provide a transactional scope using asyncpg."""
        conn = current_connection.get()
        if conn is not None:
            yield conn
            return

        async with self.pool.acquire() as connection:
            transaction = connection.transaction()
            await transaction.start()
            token = current_connection.set(connection)
            try:
                yield connection
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                raise e
            finally:
                current_connection.reset(token)
