from django.db.backends.mysql.operations import DatabaseOperations as MySQLDatabaseOperations


class DatabaseOperations(MySQLDatabaseOperations):
    compiler_module = "jumpserver.rewriting.db_backends.mysql.compiler"
