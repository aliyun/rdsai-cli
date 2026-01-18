"""DuckDB URL parser and file loader.

Supports:
- URL parsing for DuckDB connection protocols:
  - file:// - Local file paths
  - http:// - HTTP file URLs
  - https:// - HTTPS file URLs
  - duckdb:// - DuckDB database files or in-memory mode
- File loading into DuckDB tables (CSV, Excel .xlsx)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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

    @classmethod
    def is_local_file_path(cls, path: str) -> bool:
        """
        Check if a string is a valid local file path (without protocol).

        Args:
            path: The path to check

        Returns:
            True if it appears to be a local file path, False otherwise
        """
        path = path.strip()
        if not path:
            return False

        # Check if it has a protocol header
        if cls.has_protocol(path):
            return False

        # Check if it has a supported file extension
        path_obj = Path(path)
        ext = path_obj.suffix.lower()
        return ext in DuckDBFileLoader.SUPPORTED_EXTENSIONS

    @classmethod
    def is_bare_filename(cls, path: str) -> bool:
        """
        Check if a string is a bare filename (no path separators).

        Args:
            path: The path to check

        Returns:
            True if it's a bare filename, False otherwise
        """
        path = path.strip()
        if not path:
            return False

        # Check if it has a protocol header
        if cls.has_protocol(path):
            return False

        # Check if it has a supported file extension
        path_obj = Path(path)
        ext = path_obj.suffix.lower()
        if ext not in DuckDBFileLoader.SUPPORTED_EXTENSIONS:
            return False

        # Check if it contains path separators
        # On Windows, also check for drive letter (e.g., C:)
        normalized = path.replace("\\", "/")

        # Not a bare filename if:
        # - Contains path separator (/)
        # - Starts with ./ or ../
        # - Starts with / (absolute path)
        # - Contains : (Windows drive letter, e.g., C:)
        if "/" in normalized:
            return False
        if normalized.startswith("./") or normalized.startswith("../"):
            return False
        if normalized.startswith("/"):
            return False
        # Check for Windows drive letter (e.g., C:)
        # Note: URL schemes are already filtered by has_protocol() above
        if ":" in path:
            # Check if it's a Windows drive letter pattern (single letter followed by :)
            parts = path.split(":", 1)
            if len(parts) == 2 and len(parts[0]) == 1 and parts[0].isalpha():
                return False

        return True

    @classmethod
    def resolve_file_path(cls, path: str) -> str:
        """
        Resolve file path, handling bare filenames by searching in current working directory.

        Args:
            path: File path or bare filename

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If file not found
        """
        path = path.strip()
        if not path:
            raise ValueError("File path cannot be empty")

        # Check if it's a bare filename
        if cls.is_bare_filename(path):
            # Search in current working directory
            cwd = Path.cwd()
            full_path = cwd / path

            if not full_path.exists():
                raise ValueError(
                    f"File not found: {path}\nSearched in: {cwd}\nUse absolute path or relative path (e.g., ./{path})"
                )

            if not full_path.is_file():
                raise ValueError(f"Path exists but is not a file: {path}\nFound at: {full_path}")

            return str(full_path.resolve())

        # For non-bare filenames, use existing path resolution
        path_obj = Path(path).expanduser()

        if not path_obj.exists():
            raise ValueError(f"File not found: {path}")

        if not path_obj.is_file():
            raise ValueError(f"Path exists but is not a file: {path}")

        return str(path_obj.resolve())

    @classmethod
    def normalize_local_path(cls, path: str) -> str:
        """
        Normalize a local file path to a file:// URL.

        Args:
            path: Local file path (without protocol)

        Returns:
            Normalized file:// URL

        Raises:
            ValueError: If the path is invalid
        """
        path = path.strip()
        if not path:
            raise ValueError("File path cannot be empty")

        # Normalize path separators (convert backslashes to forward slashes on Windows)
        normalized_path = path.replace("\\", "/")

        # Construct file:// URL
        # For absolute paths: file:///path/to/file
        # For relative paths: file://./path/to/file or file://path/to/file
        if normalized_path.startswith("/"):
            # Absolute path
            return f"file://{normalized_path}"
        elif normalized_path.startswith("./") or normalized_path.startswith("../"):
            # Relative path starting with ./ or ../
            return f"file://{normalized_path}"
        else:
            # Relative path without ./ prefix
            return f"file://./{normalized_path}"


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
        ".xlsx": "excel",
        ".xls": "excel_legacy",  # For detection only, not actually supported
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
            File format (csv or excel)

        Raises:
            UnsupportedFileFormatError: If file format is not supported
        """
        parsed = urlparse(url)
        path = parsed.path
        ext = Path(path).suffix.lower()

        # Special handling for legacy Excel format (.xls)
        if ext == ".xls":
            raise UnsupportedFileFormatError(
                f"Unsupported file format: {ext}\n"
                f"Excel 97-2003 format (.xls) is not supported.\n"
                f"Please convert to .xlsx format (Excel 2007+) or use a different file format.\n"
                f"Supported formats: csv, excel (.xlsx)"
            )

        if ext not in cls.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(set(cls.SUPPORTED_EXTENSIONS.values())))
            # Filter out excel_legacy from display
            supported_display = [f for f in supported.split(", ") if f != "excel_legacy"]
            supported = ", ".join(supported_display) if supported_display else supported
            raise UnsupportedFileFormatError(
                f"Unsupported file format: {ext}\n"
                f"Supported formats: {supported}\n"
                f"Supported extensions: {', '.join([k for k in cls.SUPPORTED_EXTENSIONS if k != '.xls'])}"
            )

        format_type = cls.SUPPORTED_EXTENSIONS[ext]
        # Return "excel" for both .xlsx and .xls (though .xls is caught above)
        if format_type == "excel_legacy":
            format_type = "excel"

        return format_type

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
                    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')")
                elif file_format == "excel":
                    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_xlsx('{file_path}')")
            elif parsed_url.is_http_protocol:
                # HTTP/HTTPS URL
                file_url = parsed_url.path
                # Load file from URL based on format
                if file_format == "csv":
                    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_url}')")
                elif file_format == "excel":
                    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_xlsx('{file_url}')")

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
            error_msg = str(e).lower()
            # Check for Excel extension related errors
            if file_format == "excel" and (
                "excel" in error_msg or "extension" in error_msg or "read_xlsx" in error_msg or "function" in error_msg
            ):
                raise FileLoadError(
                    f"Failed to load Excel file: {e}\n"
                    f"Make sure DuckDB excel extension is available. "
                    f"DuckDB should auto-load the extension, but if this error persists, "
                    f"you may need to install it manually or check your DuckDB installation."
                ) from e
            raise FileLoadError(f"Failed to load file: {e}") from e

    @classmethod
    def load_files(
        cls,
        conn: duckdb.DuckDBPyConnection,
        parsed_urls: list[ParsedDuckDBURL],
    ) -> list[tuple[str, int, int]]:
        """
        Load multiple files into DuckDB tables.

        Args:
            conn: DuckDB connection
            parsed_urls: List of parsed URL information

        Returns:
            List of tuples (table_name, row_count, column_count) for each successfully loaded file

        Raises:
            FileLoadError: If any file loading fails (after attempting all files)
        """
        load_results: list[tuple[str, int, int]] = []
        errors: list[str] = []
        used_table_names: set[str] = set()

        for parsed_url in parsed_urls:
            try:
                # Infer table name
                base_table_name = cls.infer_table_name(parsed_url.original_url)

                # Handle table name conflicts
                table_name = base_table_name
                counter = 1
                while table_name in used_table_names:
                    table_name = f"{base_table_name}_{counter}"
                    counter += 1

                used_table_names.add(table_name)

                # Load the file
                result = cls.load_file(conn, parsed_url, table_name)
                load_results.append(result)
            except (UnsupportedFileFormatError, FileLoadError) as e:
                errors.append(f"{parsed_url.original_url}: {e}")
            except Exception as e:
                errors.append(f"{parsed_url.original_url}: {e}")

        # If all files failed, raise an error
        if not load_results and errors:
            error_msg = "Failed to load all files:\n" + "\n".join(f"  - {err}" for err in errors)
            raise FileLoadError(error_msg)

        # If some files failed, log warnings but return successful loads
        if errors:
            logger.warning(
                "Some files failed to load:\n%s",
                "\n".join(f"  - {err}" for err in errors),
            )

        return load_results
