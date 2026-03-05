from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

from .operations import DatabaseOperations


class DatabaseWrapper(MySQLDatabaseWrapper):
    ops_class = DatabaseOperations
