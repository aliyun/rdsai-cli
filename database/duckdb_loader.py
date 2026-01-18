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
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, unquote

import duckdb

from utils.logging import logger

# Large file threshold: 1GB
LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024  # 1GB


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
    def _get_file_size(cls, parsed_url: ParsedDuckDBURL) -> int:
        """
        Get file size in bytes.

        Args:
            parsed_url: Parsed URL information

        Returns:
            File size in bytes

        Raises:
            FileLoadError: If file size cannot be determined
        """
        if parsed_url.is_file_protocol:
            file_path = parsed_url.path
            if not os.path.exists(file_path):
                raise FileLoadError(f"File not found: {file_path}")
            return os.path.getsize(file_path)
        elif parsed_url.is_http_protocol:
            # For HTTP/HTTPS URLs, try to get Content-Length header
            import urllib.request
            import urllib.error

            # Use HEAD request to get Content-Length
            req = urllib.request.Request(parsed_url.path, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        return int(content_length)
                    # If Content-Length not available, raise error
                    raise FileLoadError(
                        f"Cannot determine file size for HTTP URL: {parsed_url.path}\n"
                        f"Content-Length header is not available. "
                        f"Please ensure the server provides Content-Length header or use a local file."
                    )
            except urllib.error.URLError as e:
                raise FileLoadError(
                    f"Failed to get file size from HTTP URL: {parsed_url.path}\n"
                    f"Error: {e}\n"
                    f"Please check the URL is accessible and try again."
                ) from e
            except Exception as e:
                raise FileLoadError(f"Failed to determine file size for HTTP URL: {parsed_url.path}\nError: {e}") from e
        else:
            raise FileLoadError(f"Cannot determine file size for protocol: {parsed_url.protocol}")

    @classmethod
    def _create_temp_db_file(cls, filename: str) -> str:
        """
        Create a temporary DuckDB database file.

        Args:
            filename: Filename to use as base name (without extension).

        Returns:
            Path to the temporary database file

        Raises:
            ValueError: If filename is empty or invalid
        """
        if not filename:
            raise ValueError("Filename is required for creating temporary database file")

        from config.base import get_share_dir

        temp_dir = get_share_dir() / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename based on source file name
        timestamp = int(time.time())

        # Extract base name from filename (remove extension and path)
        base_name = Path(filename).stem
        # Sanitize filename (replace invalid characters with underscore)
        base_name = "".join(c if c.isalnum() or c == "_" else "_" for c in base_name)
        # Ensure it starts with a letter or underscore
        if base_name and not (base_name[0].isalpha() or base_name[0] == "_"):
            base_name = f"_{base_name}"

        if not base_name:
            raise ValueError(f"Invalid filename: {filename} (cannot extract valid base name)")

        db_file = temp_dir / f"{base_name}_{timestamp}.duckdb"

        return str(db_file)

    @classmethod
    def _format_file_size(cls, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

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
    ) -> tuple[str, int, int, str | None]:
        """
        Load a file into a DuckDB table.

        Args:
            conn: DuckDB connection (may be replaced for large files)
            parsed_url: Parsed URL information
            table_name: Optional table name (if None, inferred from URL)

        Returns:
            Tuple of (table_name, row_count, column_count, persistent_db_path)
            persistent_db_path is None for small files, path string for large files

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

            # Get file size and determine strategy
            file_size = cls._get_file_size(parsed_url)
            is_large_file = file_size >= LARGE_FILE_THRESHOLD

            # Get file source (path or URL)
            file_source = cls._get_file_source(parsed_url)

            if is_large_file:
                # Large file: use persistent database
                if not parsed_url.original_url:
                    raise FileLoadError("Cannot create temporary database: original URL is missing")
                filename = os.path.basename(parsed_url.original_url)
                persistent_db_path = cls._create_temp_db_file(filename)
                persistent_conn = duckdb.connect(persistent_db_path)

                try:
                    # Load with progress bar
                    cls._load_large_file_with_progress(persistent_conn, file_source, table_name, file_format, file_size)

                    # Get row and column count
                    row_count, column_count = cls._get_table_stats(persistent_conn, table_name)
                    return table_name, row_count, column_count, persistent_db_path
                finally:
                    # Close the persistent connection (will be reopened by caller)
                    persistent_conn.close()
            else:
                # Small file: use existing memory connection
                cls._create_table_from_file(conn, table_name, file_source, file_format)

                # Get row and column count
                row_count, column_count = cls._get_table_stats(conn, table_name)
                return table_name, row_count, column_count, None

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
    def _get_file_source(cls, parsed_url: ParsedDuckDBURL) -> str:
        """Get file source path or URL from parsed URL."""
        if parsed_url.is_file_protocol:
            file_path = parsed_url.path
            if not os.path.exists(file_path):
                raise FileLoadError(f"File not found: {file_path}")
            return file_path
        elif parsed_url.is_http_protocol:
            return parsed_url.path
        else:
            raise FileLoadError(f"Cannot load file for protocol: {parsed_url.protocol}")

    @classmethod
    def _create_table_from_file(
        cls, conn: duckdb.DuckDBPyConnection, table_name: str, file_source: str, file_format: str
    ) -> None:
        """Create a table from a file source."""
        if file_format == "csv":
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_source}')")
        elif file_format == "excel":
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_xlsx('{file_source}')")

    @classmethod
    def _get_table_stats(cls, conn: duckdb.DuckDBPyConnection, table_name: str) -> tuple[int, int]:
        """Get row count and column count for a table."""
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        row_count = result[0] if result else 0

        result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        column_count = len(result) if result else 0

        return row_count, column_count

    @classmethod
    def _load_large_file_with_progress(
        cls,
        conn: duckdb.DuckDBPyConnection,
        file_source: str,
        table_name: str,
        file_format: str,
        file_size: int,
    ) -> None:
        """
        Load a large file into DuckDB with progress indication.

        Args:
            conn: DuckDB connection (persistent database)
            file_source: File path or URL
            table_name: Table name
            file_format: File format (csv or excel)
            file_size: File size in bytes
        """
        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            TransferSpeedColumn,
            TimeElapsedColumn,
        )
        from ui.console import console
        import threading

        file_size_str = cls._format_file_size(file_size)
        filename = os.path.basename(file_source) if os.path.exists(file_source) else file_source

        # Use enhanced spinner-based progress with speed
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TransferSpeedColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Loading large file {filename} ({file_size_str})...",
                total=file_size,  # Set total to file size for FileSizeColumn and TransferSpeedColumn
            )

            # Track progress in a separate thread
            loading_complete = threading.Event()
            loading_error = [None]
            start_time = time.time()

            def monitor_progress():
                """Monitor file reading progress by estimating based on elapsed time."""
                last_processed = 0
                while not loading_complete.is_set():
                    try:
                        # Estimate progress based on time elapsed
                        # This is a rough estimate since we can't get real progress from DuckDB
                        elapsed = time.time() - start_time

                        if elapsed > 0:
                            # Use a logarithmic curve to simulate realistic progress
                            # This gives a more realistic feel than linear progress
                            # Formula: progress = total * (1 - 1/(1 + elapsed * factor))
                            # Adjust factor based on file size (larger files process faster relatively)
                            factor = max(0.05, min(0.2, file_size / (10 * 1024 * 1024 * 1024)))  # Scale factor
                            estimated_progress = min(
                                file_size * (1 - (1 / (1 + elapsed * factor))),
                                file_size * 0.98,  # Cap at 98% until complete
                            )

                            if estimated_progress > last_processed:
                                advance = int(estimated_progress - last_processed)
                                progress.update(task, advance=advance)
                                last_processed = estimated_progress
                    except Exception:
                        pass
                    time.sleep(0.1)  # Update every 100ms

            def load_file():
                """Load file in background thread."""
                try:
                    cls._create_table_from_file(conn, table_name, file_source, file_format)
                    loading_complete.set()
                except Exception as e:
                    loading_error[0] = e
                    loading_complete.set()

            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()

            # Start loading thread
            load_thread = threading.Thread(target=load_file, daemon=True)
            load_thread.start()

            # Wait for completion (with timeout)
            load_thread.join(timeout=3600)  # 1 hour timeout

            # Stop monitoring
            loading_complete.set()
            monitor_thread.join(timeout=1)

            # Check for errors
            if loading_error[0]:
                progress.update(task, description=f"[red]Failed to load {filename}[/red]")
                raise loading_error[0]

            if not load_thread.is_alive():
                # Loading completed successfully
                progress.update(task, completed=file_size)
            else:
                # Timeout
                raise FileLoadError(f"File loading timed out after 1 hour: {filename}")

    @classmethod
    def load_files(
        cls,
        conn: duckdb.DuckDBPyConnection,
        parsed_urls: list[ParsedDuckDBURL],
    ) -> list[tuple[str, int, int, str | None]]:
        """
        Load multiple files into DuckDB tables.

        Args:
            conn: DuckDB connection
            parsed_urls: List of parsed URL information

        Returns:
            List of tuples (table_name, row_count, column_count, persistent_db_path)
            for each successfully loaded file

        Raises:
            FileLoadError: If any file loading fails (after attempting all files)
        """
        load_results: list[tuple[str, int, int, str | None]] = []
        errors: list[str] = []
        used_table_names: set[str] = set()
        persistent_db_path: str | None = None

        for parsed_url in parsed_urls:
            try:
                # Infer table name and resolve conflicts
                base_table_name = cls.infer_table_name(parsed_url.original_url)
                table_name = cls._resolve_table_name(base_table_name, used_table_names)
                used_table_names.add(table_name)

                # Check if we need persistent database for this file
                file_size = cls._get_file_size(parsed_url)
                is_large_file = file_size >= LARGE_FILE_THRESHOLD

                # For large files, use persistent database (create once, reuse)
                if is_large_file and persistent_db_path is None:
                    if not parsed_url.original_url:
                        raise FileLoadError(
                            f"Cannot create temporary database for {parsed_url.path}: original URL is missing"
                        )
                    filename = os.path.basename(parsed_url.original_url)
                    persistent_db_path = cls._create_temp_db_file(filename)
                    conn = duckdb.connect(persistent_db_path)
                elif is_large_file and persistent_db_path:
                    # Reuse existing persistent connection
                    conn = duckdb.connect(persistent_db_path)

                # Load the file
                result = cls.load_file(conn, parsed_url, table_name)
                table_name_result, row_count, column_count, file_persistent_db = result

                # Use the persistent_db_path from first large file for all files
                if file_persistent_db:
                    persistent_db_path = file_persistent_db

                load_results.append((table_name_result, row_count, column_count, persistent_db_path))
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

    @classmethod
    def _resolve_table_name(cls, base_table_name: str, used_table_names: set[str]) -> str:
        """Resolve table name conflicts by appending counter if needed."""
        table_name = base_table_name
        counter = 1
        while table_name in used_table_names:
            table_name = f"{base_table_name}_{counter}"
            counter += 1
        return table_name
