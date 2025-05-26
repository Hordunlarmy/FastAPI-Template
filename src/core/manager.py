from datetime import datetime
from typing import Any

from src import CustomError, Database, database, logger
from src.utils.filter import filter_valid_fields


class BaseManager:

    def __init__(self, db: Database = database):
        self.db = db

    @classmethod
    async def record_exists(
        cls,
        table: str,
        value: Any,
        column: str = "id",
        db: Database = database,
    ) -> bool:
        """
        Check if a record exists in a table.
        """

        query = f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {column} = $1)"
        result = await db.select(query, (value,), format=False)
        if not result:
            return False
        return result[1][0][0]

    async def _verify_record(self, table: str, record_id: int):
        """
        Check if a record exists in a table.
        """
        if not await self.record_exists(table, record_id):
            raise CustomError("Record not found", 404)

    async def create_data(self, table: str, data, returning: list = None):
        """
        Create new records in the database in bulk.
        """
        if not isinstance(data, list):
            data = [data]

        try:
            for record in data:
                record["created_at"] = datetime.now()

            allowed_fields = await self._get_table_columns(table)

            filtered_data = [
                filter_valid_fields(record, allowed_fields) for record in data
            ]

            if not filtered_data:
                raise CustomError("No valid data to insert.", 400)

            columns = ", ".join(filtered_data[0].keys())

            placeholders = []
            for i in range(len(filtered_data)):
                offset = i * len(filtered_data[0])
                placeholder_values = [
                    f"${offset + j + 1}" for j in range(len(filtered_data[0]))
                ]
                placeholders.append(f"({', '.join(placeholder_values)})")

            values_placeholder = ", ".join(placeholders)

            values = [
                value for record in filtered_data for value in record.values()
            ]

            if returning is None:
                returning = ["id"]

            returning_clause = (
                f"RETURNING {', '.join(returning)}" if returning else ""
            )

            query = f"""
                INSERT INTO {table} ({columns})
                VALUES {values_placeholder}
                ON CONFLICT DO NOTHING
                {returning_clause}
            """

        except CustomError as e:
            raise e

        except Exception as e:
            logger.error(f"Error: {e}")
            raise CustomError(f"Failed to create data: {e}", 500)
        response = await self.db.commit(query, values)
        if len(data) >= 1 and response:
            entity_id = (
                response.get("id")
                if isinstance(response, dict)
                else response[0].get("id")
            )
            data[0]["entity_id"] = str(entity_id) if entity_id else None
            if table not in ["activities"]:
                await self.log_activity(table, "create", data[0])
            return response

        else:
            logger.info(
                f"No new record inserted for {table}. Possible conflict."
            )
            return None

    async def update_data(self, table, record_id, data):
        """
        Update a record in the database.
        """

        await self._verify_record(table, record_id)
        data["updated_at"] = datetime.now()

        try:
            data["updated_at"] = datetime.now()
            allowed_fields = await self._get_table_columns(table)
            filtered_data = filter_valid_fields(data, allowed_fields)

            set_values = ", ".join(
                f"{key}=${i + 2}" for i, key in enumerate(filtered_data.keys())
            )
            query = f"""
                UPDATE {table}
                SET {set_values}
                WHERE id = $1
                RETURNING id
            """
        except CustomError as e:
            raise e

        except Exception as e:
            logger.error(f"Error: {e}")
            raise CustomError(f"Failed to update data: {e}", 500)

        response = await self.db.commit(
            query, [record_id] + list(filtered_data.values())
        )
        if response:
            data["entity_id"] = str(record_id)
            if table not in ["activities"]:
                await self.log_activity(table, "update", data)
            return response
        else:
            logger.info(
                f"No record updated for {table} with ID {record_id}. "
                f"Possible conflict."
            )
            return None

    async def delete_data(self, table, record_ids: list):
        """
        Delete multiple records from the database.
        """

        try:
            if not record_ids:
                return False

            placeholders = ", ".join(
                f"${i + 1}" for i in range(len(record_ids))
            )
            query = f"DELETE FROM {table} WHERE id IN ({placeholders})"

            await self.db.commit(query, tuple(record_ids))
            return True
        except CustomError as e:
            raise e
        except Exception as e:
            logger.error(f"Error: {e}")
            raise CustomError(f"Failed to delete data: {e}", 500)

    async def get_data(
        self, table, filters: dict = None, columns: list = None
    ):
        """
        Fetch records from the database with optional filtering, sorting,
        pagination, and column selection.
        """

        filters = filters or {}
        columns = columns or ["*"]
        id = filters.get("id")

        if id is not None:
            await self._verify_record(table, id)
            query = f"SELECT {', '.join(columns)} FROM {table} WHERE id = $1"
            result = await self.db.select(query, (id,))
            return result[0] if result else None

        allowed_fields = await self._get_table_columns(table)
        page = int(filters.get("page", 1))
        page_size = int(filters.get("page_size", 10))

        sort_by = filters.get("sort_by") or "priority"
        order_by = filters.get("order_by") or "ASC"
        if sort_by == "priority" and sort_by not in allowed_fields:
            sort_by = "updated_at"
            order_by = "DESC"

        allowed_sort_columns = {
            "id",
            "name",
            "created_at",
            "priority",
            "updated_at",
        }
        sort_by = sort_by if sort_by in allowed_sort_columns else "updated_at"
        order_by = "DESC" if order_by.upper() == "DESC" else "ASC"

        conditions, params = [], []

        filtered_items = [
            (key, value)
            for key, value in filters.items()
            if key not in {"page", "page_size", "sort_by", "order_by"}
        ]

        for idx, (key, value) in enumerate(filtered_items):
            cast = "::uuid" if key.endswith("_id") else ""
            conditions.append(f"t.{key} = ${idx + 1}{cast}")
            params.append(value)

        query_conditions = " AND ".join(conditions) if conditions else "1=1"

        count_query = (
            f"SELECT COUNT(*) AS total FROM {table} t WHERE {query_conditions}"
        )
        total_count = await self._get_count(count_query, params)

        offset = (page - 1) * page_size
        query = f"""
            SELECT {", ".join(columns)}
            FROM {table} t
            WHERE {query_conditions}
            ORDER BY t.{sort_by} {order_by}, t.updated_at ASC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        params.extend([page_size, offset])

        try:
            results = await self.db.select(query, tuple(params))
            return await self._pagination_response(
                results, total_count, page, page_size
            )
        except CustomError as e:
            raise e
        except Exception as e:
            logger.error(f"Error fetching {table} data: {e}")
            raise CustomError(
                f"An error occurred while fetching {table} data.", 500
            )

    async def _get_table_columns(self, table_name: str):
        """
        Fetch column names for a given table from the database.
        """
        try:
            query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = $1
            """
            rows = await self.db.select(query, [table_name])
            return {row["column_name"] for row in rows}
        except CustomError as e:
            raise e
        except Exception as e:
            logger.error(
                f"Failed to fetch table columns for '{table_name}': {e}"
            )
            raise CustomError("Failed to fetch table columns", 500) from e

    async def _get_count(self, query, params):
        try:
            total_data = await self.db.select(query, tuple(params))
            return total_data[0]["total"] if total_data else 0
        except CustomError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to fetch count: {e}")
            raise CustomError("Failed to fetch count", 500) from e

    async def _pagination_response(self, data, total_count, page, page_size):
        try:
            total_pages = (total_count // page_size) + (
                1 if total_count % page_size > 0 else 0
            )
            total_pages = max(total_pages, 1) if total_count > 0 else 0

            return {
                "data": data,
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total": total_count,
                    "total_pages": total_pages,
                },
            }
        except CustomError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to generate pagination response: {e}")
            raise CustomError("Failed to paginate results", 500) from e
