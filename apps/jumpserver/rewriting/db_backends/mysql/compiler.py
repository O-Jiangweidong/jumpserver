from datetime import datetime

from django.core.exceptions import EmptyResultSet
from django.conf import settings
from django.db.models.sql import compiler
from django.db.models.sql.constants import (
    CURSOR,
    GET_ITERATOR_CHUNK_SIZE,
    MULTI,
    NO_RESULTS,
    SINGLE,
)

from django.db.backends.mysql.compiler import (
    SQLCompiler as MySQLCompiler,
    SQLInsertCompiler as MySQLInsertCompiler,
    SQLDeleteCompiler as MySQLDeleteCompiler,
    SQLUpdateCompiler as MySQLUpdateCompiler,
    SQLAggregateCompiler as MySQLAggregateCompiler,
)

from . import consts as c
from ..middleman import MiddlemanClient
from jumpserver.utils import current_request as request


class MockCursor(object):
    def __init__(self, rowcount=0):
        self.rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def close(self):
        pass


class Mixin:
    query: type
    model: type

    def _get_table_name(self):
        try:
            table_name = self.query.base_table
            if not table_name:
                table_name = self.query.model._meta.db_table
        except Exception as error:
            table_name = ''
        return table_name

    @staticmethod
    def _datetime_parser(obj):
        if not obj or not isinstance(obj, str):
            return obj

        try:
            dt_with_tz = datetime.fromisoformat(obj)
            return dt_with_tz.replace(tzinfo=None)
        except: # noqa
            return obj

    def handle_special_formats(self, result):
        if isinstance(result, list) and len(result) > 0 and result[0]:
            outer = []
            for i in result[0]:
                inner = []
                for j in i:
                    inner.append(self._datetime_parser(j))
                outer.append(inner)
            result[0] = outer
        return result

    def send_middleman(self, sql, params, sql_type):
        result, replica_name = None, None
        if request:
            replica_name = request.headers.get('x-replica-name')
            if request.path == '/api/v1/common/middleman/exec-sql/':
                return True, result

            if not getattr(request, 'can_middleman', False):
                return True, result

        table_name = self._get_table_name()
        if table_name in c.MIDDLEMAN_TABLE_BLACKLIST:
            return False, result

        client = MiddlemanClient()
        if settings.MIDDLEMAN_SERVICE_ROLE.lower() == 'master':
            if not replica_name:
                return True, result

            result = client.sql_sync(replica_name, sql_type, sql, params)
            result = self.handle_special_formats(result)
            return False, result
        elif settings.MIDDLEMAN_SERVICE_ROLE.lower() == 'replica' and sql_type != c.SELECT:
            # TODO 给 middleman 发送过去即可
            client.sql_sync(replica_name, sql_type, sql, params)
            return True, result
        else:
            return True, result


class SQLCompiler(Mixin, MySQLCompiler):
    SQL_TYPE = c.SELECT

    def execute_sql(
        self, result_type=MULTI, chunked_fetch=False, chunk_size=GET_ITERATOR_CHUNK_SIZE
    ):
        result_type = result_type or NO_RESULTS
        try:
            sql, params = self.as_sql()
            if not sql:
                raise EmptyResultSet
        except EmptyResultSet:
            if result_type == MULTI:
                return iter([])
            else:
                return

        can_next, result = self.send_middleman(sql, params, self.SQL_TYPE)
        if not can_next:
            if result_type == MULTI:
                return result or []
            elif result_type == SINGLE and isinstance(result, (tuple, list)):
                try:
                    return result[0][0]
                except: # noqa
                    return result[0]
            elif isinstance(result, dict):
                return MockCursor(result.get('rowcount', 0))
            return result or None

        if chunked_fetch:
            cursor = self.connection.chunked_cursor()
        else:
            cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params)
        except Exception:
            cursor.close()
            raise

        if result_type == CURSOR:
            return cursor
        if result_type == SINGLE:
            try:
                val = cursor.fetchone()
                if val:
                    return val[0: self.col_count]
                return val
            finally:
                cursor.close()
        if result_type == NO_RESULTS:
            cursor.close()
            return

        result = compiler.cursor_iter(
            cursor,
            self.connection.features.empty_fetchmany_value,
            self.col_count if self.has_extra_select else None,
            chunk_size,
        )
        if not chunked_fetch or not self.connection.features.can_use_chunked_reads:
            return list(result)
        return result


class SQLInsertCompiler(Mixin, MySQLInsertCompiler):
    SQL_TYPE = c.INSERT

    def execute_sql(self, returning_fields=None):
        assert not (
                returning_fields
                and len(self.query.objs) != 1
                and not self.connection.features.can_return_rows_from_bulk_insert
        )
        opts = self.query.get_meta()
        self.returning_fields = returning_fields
        with self.connection.cursor() as cursor:
            can_next = True
            for sql, params in self.as_sql():
                can_next, _ = self.send_middleman(sql, params, self.SQL_TYPE)
                if can_next:
                    cursor.execute(sql, params)
            if not can_next:
                return []

            if not self.returning_fields:
                return []
            if (
                    self.connection.features.can_return_rows_from_bulk_insert
                    and len(self.query.objs) > 1
            ):
                rows = self.connection.ops.fetch_returned_insert_rows(cursor)
            elif self.connection.features.can_return_columns_from_insert:
                assert len(self.query.objs) == 1
                rows = [
                    self.connection.ops.fetch_returned_insert_columns(
                        cursor,
                        self.returning_params,
                    )
                ]
            else:
                rows = [
                    (
                        self.connection.ops.last_insert_id(
                            cursor,
                            opts.db_table,
                            opts.pk.column,
                        ),
                    )
                ]
        cols = [field.get_col(opts.db_table) for field in self.returning_fields]
        converters = self.get_converters(cols)
        if converters:
            rows = list(self.apply_converters(rows, converters))
        return rows


class SQLDeleteCompiler(MySQLDeleteCompiler, SQLCompiler):
    SQL_TYPE = c.DELETE


class SQLUpdateCompiler(MySQLUpdateCompiler, SQLCompiler):
    SQL_TYPE = c.UPDATE

    def execute_sql(self, result_type):
        cursor = SQLCompiler.execute_sql(self, result_type)
        try:
            rows = cursor.rowcount if cursor else 0
            is_empty = cursor is None
        finally:
            if hasattr(cursor, 'close'):
                cursor.close()
        for query in self.query.get_related_updates():
            aux_rows = query.get_compiler(self.using).execute_sql(result_type)
            if is_empty and aux_rows:
                rows = aux_rows
                is_empty = False
        return rows


class SQLAggregateCompiler(MySQLAggregateCompiler):
    SQL_TYPE = c.AGGREGATE
