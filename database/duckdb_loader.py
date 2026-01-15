"""DuckDB URL parser and file loader.

Supports:
- URL parsing for DuckDB connection protocols:
  - file:// - Local file paths
  - http:// - HTTP file URLs
  - https:// - HTTPS file URLs
  - duckdb:// - DuckDB database files or in-memory mode
- File loading into DuckDB tables (CSV, Parquet, JSON)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

import duckdb

from utils.logging import logger


# ========== URL Parser ==========


class DuckDBProtocol(str, Enum):
    """Supported DuckDB connection protocols."""

    FILE = "file"
    HTTP = "http"
    HTTPS = "https"
    DUCKDB = "duckdb"


@dataclass
class ParsedDuckDBURL:
    """Parsed DuckDB URL information."""

    protocol: DuckDBProtocol
    path: str
    is_memory: bool = False
    original_url: str = ""

    @property
    def is_file_protocol(self) -> bool:
        """Check if this is a file:// protocol."""
        return self.protocol == DuckDBProtocol.FILE

    @property
    def is_http_protocol(self) -> bool:
        """Check if this is an http:// or https:// protocol."""
        return self.protocol in (DuckDBProtocol.HTTP, DuckDBProtocol.HTTPS)

    @property
    def is_duckdb_protocol(self) -> bool:
        """Check if this is a duckdb:// protocol."""
        return self.protocol == DuckDBProtocol.DUCKDB

    @property
    def url(self) -> str:
        """Get the full URL."""
        if self.protocol == DuckDBProtocol.DUCKDB:
            if self.is_memory:
                return "duckdb://:memory:"
            return f"duckdb://{self.path}"
        elif self.protocol == DuckDBProtocol.FILE:
            return f"file://{self.path}"
        else:
            return f"{self.protocol.value}://{self.path}"


class DuckDBURLParser:
    """Parser for DuckDB connection URLs."""

    SUPPORTED_PROTOCOLS = {
        "file": DuckDBProtocol.FILE,
        "http": DuckDBProtocol.HTTP,
        "https": DuckDBProtocol.HTTPS,
        "duckdb": DuckDBProtocol.DUCKDB,
    }

    @classmethod
    def parse(cls, url: str) -> ParsedDuckDBURL:
        """
        Parse a DuckDB URL into its components.

        Args:
            url: The URL to parse (e.g., "file:///path/to/file.csv")

        Returns:
            ParsedDuckDBURL object with protocol and path information

        Raises:
            ValueError: If the URL format is invalid or protocol is not supported
        """
        url = url.strip()

        if not url:
            raise ValueError("URL cannot be empty")

        # Parse the URL
        parsed = urlparse(url)

        # Check if protocol is supported
        scheme = parsed.scheme.lower()
        if scheme not in cls.SUPPORTED_PROTOCOLS:
            raise ValueError(
                f"Unsupported protocol: {scheme}://\n"
                f"Supported protocols: {', '.join(cls.SUPPORTED_PROTOCOLS.keys())}://"
            )

        protocol = cls.SUPPORTED_PROTOCOLS[scheme]

        # Handle different protocols
        if protocol == DuckDBProtocol.FILE:
            # file:// protocol
            # file:///absolute/path -> path = /absolute/path
            # file://./relative/path -> path = ./relative/path
            # file://relative/path -> path = relative/path
            path = parsed.path
            if parsed.netloc:
                # file://host/path format (uncommon but valid)
                path = f"/{parsed.netloc}{path}"
            path = unquote(path)
            return ParsedDuckDBURL(
                protocol=protocol,
                path=path,
                original_url=url,
            )

        elif protocol in (DuckDBProtocol.HTTP, DuckDBProtocol.HTTPS):
            # http:// or https:// protocol
            # Reconstruct the full URL
            full_url = f"{scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                full_url += f"?{parsed.query}"
            if parsed.fragment:
                full_url += f"#{parsed.fragment}"
            return ParsedDuckDBURL(
                protocol=protocol,
                path=full_url,
                original_url=url,
            )

        elif protocol == DuckDBProtocol.DUCKDB:
            # duckdb:// protocol
            # duckdb:///path/to/db.duckdb -> path = /path/to/db.duckdb
            # duckdb://:memory: -> is_memory = True
            path = parsed.path
            if parsed.netloc == ":memory:":
                return ParsedDuckDBURL(
                    protocol=protocol,
                    path=":memory:",
                    is_memory=True,
                    original_url=url,
                )
            elif parsed.netloc:
                # duckdb://host/path format
                path = f"/{parsed.netloc}{path}"
            path = unquote(path)
            return ParsedDuckDBURL(
                protocol=protocol,
                path=path,
                is_memory=(path == ":memory:"),
                original_url=url,
            )

        else:
            raise ValueError(f"Unhandled protocol: {protocol}")

    @classmethod
    def has_protocol(cls, url: str) -> bool:
        """
        Check if a URL has a supported protocol header.

        Args:
            url: The URL to check

        Returns:
            True if the URL starts with a supported protocol, False otherwise
        """
        url = url.strip()
        if not url:
            return False

        parsed = urlparse(url)
        return parsed.scheme.lower() in cls.SUPPORTED_PROTOCOLS

    @classmethod
    def validate_file_path(cls, path: str) -> Path:
        """
        Validate and convert a file path to a Path object.

        Args:
            path: The file path to validate

        Returns:
            Path object

        Raises:
            ValueError: If the path format is invalid
        """
        if not path:
            raise ValueError("File path cannot be empty")

        path_obj = Path(path)
        return path_obj


# ========== File Loader ==========


class UnsupportedFileFormatError(Exception):
    """Raised when file format is not supported."""

    pass


class FileLoadError(Exception):
    """Raised when file loading fails."""

    pass


class DuckDBFileLoader:
    """Loader for files into DuckDB tables."""

    SUPPORTED_EXTENSIONS = {
        ".csv": "csv",
        ".parquet": "parquet",
        ".json": "json",
        ".jsonl": "json",
    }

    @classmethod
    def infer_table_name(cls, url: str) -> str:
        """
        Infer table name from file URL or path.

        Args:
            url: File URL or path

        Returns:
            Inferred table name (without extension)
        """
        # Extract filename from URL
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)

        # Remove extension
        if "." in filename:
            name = ".".join(filename.split(".")[:-1])
        else:
            name = filename

        # Sanitize table name (replace invalid characters with underscore)
        table_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        # Ensure it starts with a letter or underscore
        if table_name and not (table_name[0].isalpha() or table_name[0] == "_"):
            table_name = f"_{table_name}"

        # Default name if empty
        if not table_name:
            table_name = "data"

        return table_name

    @classmethod
    def detect_file_format(cls, url: str) -> str:
        """
        Detect file format from URL extension.

        Args:
            url: File URL or path

        Returns:
            File format (csv, parquet, or json)

        Raises:
            UnsupportedFileFormatError: If file format is not supported
        """
        parsed = urlparse(url)
        path = parsed.path
        ext = Path(path).suffix.lower()

        if ext not in cls.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(set(cls.SUPPORTED_EXTENSIONS.values())))
            raise UnsupportedFileFormatError(
                f"Unsupported file format: {ext}\n"
                f"Supported formats: {supported}\n"
                f"Supported extensions: {', '.join(cls.SUPPORTED_EXTENSIONS.keys())}"
            )

        return cls.SUPPORTED_EXTENSIONS[ext]

    @classmethod
    def load_file(
        cls,
        conn: duckdb.DuckDBPyConnection,
        parsed_url: ParsedDuckDBURL,
        table_name: str | None = None,
    ) -> tuple[str, int, int]:
        """
        Load a file into a DuckDB table.

        Args:
            conn: DuckDB connection
            parsed_url: Parsed URL information
            table_name: Optional table name (if None, inferred from URL)

        Returns:
            Tuple of (table_name, row_count, column_count)

        Raises:
            FileLoadError: If file loading fails
        """
        if table_name is None:
            table_name = cls.infer_table_name(parsed_url.original_url)

        # Validate table name
        if not table_name or not table_name.replace("_", "").isalnum():
            raise FileLoadError(f"Invalid table name: {table_name}")

        try:
            # Detect file format
            file_format = cls.detect_file_format(parsed_url.original_url)

            # Get file path/URL
            if parsed_url.is_file_protocol:
                file_path = parsed_url.path
                # Validate file exists
                if not os.path.exists(file_path):
                    raise FileLoadError(f"File not found: {file_path}")

                # Load file based on format
                if file_format == "csv":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')"
                    )
                elif file_format == "parquet":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{file_path}')"
                    )
                elif file_format == "json":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_json_auto('{file_path}')"
                    )

            elif parsed_url.is_http_protocol:
                # HTTP/HTTPS URL
                file_url = parsed_url.path

                # Load file from URL based on format
                if file_format == "csv":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_url}')"
                    )
                elif file_format == "parquet":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{file_url}')"
                    )
                elif file_format == "json":
                    conn.execute(
                        f"CREATE TABLE {table_name} AS SELECT * FROM read_json_auto('{file_url}')"
                    )

            else:
                raise FileLoadError(f"Cannot load file for protocol: {parsed_url.protocol}")

            # Get row and column count
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = result[0] if result else 0

            result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            column_count = len(result) if result else 0

            return table_name, row_count, column_count
        except UnsupportedFileFormatError:
            raise
        except FileLoadError:
            raise
        except Exception as e:
            raise FileLoadError(f"Failed to load file: {e}") from e
