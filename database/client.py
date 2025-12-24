"""Database client abstraction and MySQL implementation."""

import re
import mysql.connector
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


# Pattern for validating SQL identifiers
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$]*$|^`[^`]+`$")


def validate_identifier(name: str) -> str:
    """
    Validate and sanitize a SQL identifier (database name, table name, etc.).

    Args:
        name: The identifier to validate

    Returns:
        The validated identifier (stripped of backticks if present)

    Raises:
        ValueError: If the identifier contains invalid characters
    """
    if not name or not name.strip():
        raise ValueError("Identifier cannot be empty")

    name = name.strip()

    # Remove surrounding backticks for validation
    if name.startswith("`") and name.endswith("`"):
        inner_name = name[1:-1]
        if "`" in inner_name:
            raise ValueError(f"Invalid identifier: {name!r} contains embedded backticks")
        return inner_name

    if not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"Invalid identifier: {name!r} contains invalid characters")

    return name


class TransactionState(Enum):
    """Transaction state enumeration."""

    NOT_IN_TRANSACTION = "NOT_IN_TRANSACTION"
    IN_TRANSACTION = "IN_TRANSACTION"
    TRANSACTION_ERROR = "TRANSACTION_ERROR"


class DatabaseClient(ABC):
    """Abstract base class for database clients."""

    @abstractmethod
    def execute(self, sql: str) -> Any:
        """Execute a SQL statement."""
        ...

    @abstractmethod
    def fetchall(self) -> list[Any]:
        """Fetch all rows from the last query."""
        ...

    @abstractmethod
    def fetchone(self) -> Any | None:
        """Fetch one row from the last query."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        ...

    @abstractmethod
    def change_database(self, database: str) -> None:
        """Change to the specified database."""
        ...

    @classmethod
    @abstractmethod
    def engine_name(cls) -> str:
        """Return the engine name (e.g., 'mysql', 'postgresql')."""
        ...

    @abstractmethod
    def get_transaction_state(self) -> TransactionState:
        """Get current transaction state."""
        ...

    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a new transaction."""
        ...

    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        ...

    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        ...

    @abstractmethod
    def set_autocommit(self, enabled: bool) -> None:
        """Set autocommit mode."""
        ...

    @abstractmethod
    def get_autocommit(self) -> bool:
        """Get current autocommit mode."""
        ...

    @abstractmethod
    def ping(self, reconnect: bool = False) -> bool:
        """Check if the connection is alive."""
        ...

    @abstractmethod
    def get_columns(self) -> list[str] | None:
        """Get column names from the last query result."""
        ...

    @abstractmethod
    def get_row_count(self) -> int:
        """Get the number of affected/returned rows from the last operation."""
        ...


class DatabaseClientFactory:
    """Factory for creating database clients."""

    _registry: dict[str, type[DatabaseClient]] = {}

    @classmethod
    def register(cls, engine: str, client_cls: type[DatabaseClient]) -> None:
        cls._registry[engine] = client_cls

    @classmethod
    def create(cls, engine: str, **kwargs: Any) -> DatabaseClient:
        if engine not in cls._registry:
            raise ValueError(f"Unsupported engine: {engine}")
        return cls._registry[engine](**kwargs)

    @classmethod
    def supported_engines(cls) -> list[str]:
        return list(cls._registry.keys())


class MySQLClient(DatabaseClient):
    """MySQL database client implementation."""

    default_port = 3306

    def __init__(
        self, host: str, port: int | None, user: str, password: str | None, database: str | None = None, **kwargs: Any
    ):
        if port is None:
            port = self.default_port

        conn_params: dict[str, Any] = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "connect_timeout": 10,
            "autocommit": True,
        }

        # Handle SSL configuration
        ssl_ca = kwargs.get("ssl_ca")
        ssl_cert = kwargs.get("ssl_cert")
        ssl_key = kwargs.get("ssl_key")
        ssl_mode = kwargs.get("ssl_mode")

        if ssl_ca or ssl_cert or ssl_key or ssl_mode:
            ssl_config: dict[str, Any] = {}
            if ssl_ca:
                ssl_config["ca"] = ssl_ca
            if ssl_cert:
                ssl_config["cert"] = ssl_cert
            if ssl_key:
                ssl_config["key"] = ssl_key
            if ssl_mode:
                ssl_config["verify_cert"] = ssl_mode.upper() in ["VERIFY_CA", "VERIFY_IDENTITY"]
                ssl_config["verify_identity"] = ssl_mode.upper() == "VERIFY_IDENTITY"
                if ssl_mode.upper() == "DISABLED":
                    conn_params["ssl_disabled"] = True
                elif ssl_mode.upper() in ["REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"]:
                    conn_params["ssl_disabled"] = False
                    conn_params["ssl_ca"] = ssl_config.get("ca")
                    conn_params["ssl_cert"] = ssl_config.get("cert")
                    conn_params["ssl_key"] = ssl_config.get("key")
                    conn_params["ssl_verify_cert"] = ssl_config.get("verify_cert", False)
                    conn_params["ssl_verify_identity"] = ssl_config.get("verify_identity", False)

        self.conn = mysql.connector.connect(**conn_params)
        self.cursor = self.conn.cursor()
        self._transaction_state = TransactionState.NOT_IN_TRANSACTION
        self._autocommit = True

    def execute(self, sql: str) -> Any:
        self.cursor.execute(sql)
        return self.cursor

    def fetchall(self) -> list[Any]:
        return self.cursor.fetchall()

    def fetchone(self) -> Any | None:
        return self.cursor.fetchone()

    def close(self) -> None:
        self.cursor.close()
        self.conn.close()

    def change_database(self, database: str) -> None:
        validated_name = validate_identifier(database)
        self.cursor.execute(f"USE `{validated_name}`;")

    @classmethod
    def engine_name(cls) -> str:
        return "mysql"

    def get_transaction_state(self) -> TransactionState:
        return self._transaction_state

    def begin_transaction(self) -> None:
        try:
            if self._transaction_state == TransactionState.IN_TRANSACTION:
                raise Exception("Already in transaction")
            self.cursor.execute("SET autocommit = 0")
            self.cursor.execute("BEGIN")
            self._transaction_state = TransactionState.IN_TRANSACTION
            self._autocommit = False
        except Exception as e:
            self._transaction_state = TransactionState.TRANSACTION_ERROR
            raise e

    def commit_transaction(self) -> None:
        try:
            if self._transaction_state != TransactionState.IN_TRANSACTION:
                raise Exception("Not in transaction")
            self.cursor.execute("COMMIT")
            self.cursor.execute("SET autocommit = 1")
            self._transaction_state = TransactionState.NOT_IN_TRANSACTION
            self._autocommit = True
        except Exception as e:
            self._transaction_state = TransactionState.TRANSACTION_ERROR
            raise e

    def rollback_transaction(self) -> None:
        try:
            if self._transaction_state not in [TransactionState.IN_TRANSACTION, TransactionState.TRANSACTION_ERROR]:
                raise Exception("Not in transaction")
            self.cursor.execute("ROLLBACK")
            self.cursor.execute("SET autocommit = 1")
            self._transaction_state = TransactionState.NOT_IN_TRANSACTION
            self._autocommit = True
        except Exception as e:
            self._transaction_state = TransactionState.TRANSACTION_ERROR
            raise e

    def set_autocommit(self, enabled: bool) -> None:
        try:
            if self._transaction_state == TransactionState.IN_TRANSACTION:
                raise Exception("Cannot change autocommit mode while in transaction")
            self.cursor.execute(f"SET autocommit = {'1' if enabled else '0'}")
            self._autocommit = enabled
            if not enabled:
                self._transaction_state = TransactionState.IN_TRANSACTION
            else:
                self._transaction_state = TransactionState.NOT_IN_TRANSACTION
        except Exception as e:
            self._transaction_state = TransactionState.TRANSACTION_ERROR
            raise e

    def get_autocommit(self) -> bool:
        return self._autocommit

    def ping(self, reconnect: bool = False) -> bool:
        try:
            self.conn.ping(reconnect=reconnect, attempts=1, delay=0)
            return True
        except Exception:
            return False

    def get_columns(self) -> list[str] | None:
        if self.cursor.description:
            return [desc[0] for desc in self.cursor.description]
        return None

    def get_row_count(self) -> int:
        return self.cursor.rowcount if self.cursor.rowcount >= 0 else -1


# Register MySQL client
DatabaseClientFactory.register("mysql", MySQLClient)
