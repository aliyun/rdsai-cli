"""MySQL InnoDB status tool for monitoring InnoDB engine status."""

from pathlib import Path
from typing import Any, override
import re

from pydantic import BaseModel

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    """No parameters needed for SHOW ENGINE INNODB STATUS."""

    pass


# Section names in priority order (higher priority sections are always included)
_HIGH_PRIORITY_SECTIONS = {
    "LATEST DETECTED DEADLOCK",
    "TRANSACTIONS",
    "SEMAPHORES",
}

_MEDIUM_PRIORITY_SECTIONS = {
    "BUFFER POOL AND MEMORY",
    "LOG",
    "ROW OPERATIONS",
}

_LOW_PRIORITY_SECTIONS = {
    "BACKGROUND THREAD",
    "FILE I/O",
    "INSERT BUFFER AND ADAPTIVE HASH INDEX",
    "INDIVIDUAL BUFFER POOL INFO",
}

# Maximum output size in characters (approximately 4KB)
_MAX_OUTPUT_SIZE = 4000


def _parse_innodb_sections(status_text: str) -> dict[str, str]:
    """Parse InnoDB status into named sections.

    InnoDB status format uses dashes and section headers like:
    --------
    SECTION NAME
    --------
    content...
    """
    sections: dict[str, str] = {}

    # Pattern to match section headers
    # Sections are delimited by lines of dashes with section name between
    section_pattern = re.compile(r"-{3,}\n([A-Z][A-Z /]+)\n-{3,}\n(.*?)(?=-{3,}\n[A-Z]|\Z)", re.DOTALL)

    for match in section_pattern.finditer(status_text):
        section_name = match.group(1).strip()
        section_content = match.group(2).strip()
        sections[section_name] = section_content

    return sections


def _extract_deadlock_summary(content: str) -> str:
    """Extract key information from deadlock section."""
    if not content:
        return "No deadlock detected."

    lines = content.split("\n")
    summary_lines = []

    # Extract timestamp and transaction info
    for line in lines[:30]:  # First 30 lines usually contain key info
        line = line.strip()
        if any(
            keyword in line.upper()
            for keyword in [
                "TRANSACTION",
                "WAITING FOR",
                "HOLDS THE LOCK",
                "RECORD LOCKS",
                "TABLE",
                "INDEX",
                "ROLLED BACK",
            ]
        ):
            summary_lines.append(line)

    if summary_lines:
        return "\n".join(summary_lines[:15])  # Max 15 lines
    return content[:500] if len(content) > 500 else content


def _extract_transaction_summary(content: str) -> str:
    """Extract key transaction information."""
    if not content:
        return "No active transactions."

    lines = content.split("\n")
    summary_lines = []

    # Extract transaction list header and active transactions
    active_count = 0
    lock_wait_count = 0

    for line in lines:
        line_stripped = line.strip()
        # Count active and lock-waiting transactions
        if "ACTIVE" in line_stripped.upper():
            active_count += 1
        if "LOCK WAIT" in line_stripped.upper():
            lock_wait_count += 1

        # Include important lines
        if any(
            keyword in line_stripped.upper()
            for keyword in ["TRX READ VIEW", "HISTORY LIST LENGTH", "LOCK WAIT", "ROLLING BACK", "COMMITTING"]
        ):
            summary_lines.append(line_stripped)

    # Build summary header
    header = f"Active transactions: {active_count}"
    if lock_wait_count > 0:
        header += f", Lock waits: {lock_wait_count} (ATTENTION!)"

    result = [header]
    if summary_lines:
        result.extend(summary_lines[:10])  # Max 10 detail lines

    return "\n".join(result)


def _extract_semaphore_summary(content: str) -> str:
    """Extract semaphore/mutex information."""
    if not content:
        return "No semaphore contention."

    lines = content.split("\n")
    summary_lines = []

    # Look for wait information
    has_waits = False
    for line in lines:
        line_stripped = line.strip()
        if "waited at" in line_stripped.lower() or "OS WAIT" in line_stripped.upper():
            has_waits = True
            summary_lines.append(line_stripped)
        elif any(kw in line_stripped for kw in ["Mutex spin", "RW-shared", "RW-excl"]):
            summary_lines.append(line_stripped)

    if not has_waits:
        return "No significant semaphore contention detected."

    return "\n".join(summary_lines[:8])  # Max 8 lines


def _extract_buffer_pool_summary(content: str) -> str:
    """Extract buffer pool statistics."""
    if not content:
        return "Buffer pool info not available."

    lines = content.split("\n")
    key_metrics = []

    for line in lines:
        line_stripped = line.strip()
        # Extract key buffer pool metrics
        if any(
            keyword in line_stripped
            for keyword in [
                "Total large memory",
                "Buffer pool size",
                "Free buffers",
                "Database pages",
                "Modified db pages",
                "Pages read",
                "hit rate",
                "young-making rate",
            ]
        ):
            key_metrics.append(line_stripped)

    return "\n".join(key_metrics[:10]) if key_metrics else content[:300]


def _extract_log_summary(content: str) -> str:
    """Extract log information."""
    if not content:
        return "Log info not available."

    lines = content.split("\n")
    key_metrics = []

    for line in lines:
        line_stripped = line.strip()
        if any(
            keyword in line_stripped
            for keyword in ["Log sequence number", "Log flushed up to", "Last checkpoint", "pending log", "log i/o"]
        ):
            key_metrics.append(line_stripped)

    return "\n".join(key_metrics[:6]) if key_metrics else content[:200]


def _build_optimized_output(sections: dict[str, str]) -> str:
    """Build optimized output with key sections summarized."""
    output_parts = []

    # Always include summary header
    output_parts.append("=== InnoDB Status Summary ===\n")

    # High priority sections (always included, may be summarized)
    if "LATEST DETECTED DEADLOCK" in sections:
        content = sections["LATEST DETECTED DEADLOCK"]
        output_parts.append("## DEADLOCK INFO")
        output_parts.append(_extract_deadlock_summary(content))
        output_parts.append("")
    else:
        output_parts.append("## DEADLOCK: None detected\n")

    if "TRANSACTIONS" in sections:
        output_parts.append("## TRANSACTIONS")
        output_parts.append(_extract_transaction_summary(sections["TRANSACTIONS"]))
        output_parts.append("")

    if "SEMAPHORES" in sections:
        output_parts.append("## SEMAPHORES")
        output_parts.append(_extract_semaphore_summary(sections["SEMAPHORES"]))
        output_parts.append("")

    # Medium priority sections
    if "BUFFER POOL AND MEMORY" in sections:
        output_parts.append("## BUFFER POOL")
        output_parts.append(_extract_buffer_pool_summary(sections["BUFFER POOL AND MEMORY"]))
        output_parts.append("")

    if "LOG" in sections:
        output_parts.append("## LOG")
        output_parts.append(_extract_log_summary(sections["LOG"]))
        output_parts.append("")

    # Add note about full output availability
    output_parts.append("---")
    output_parts.append("Note: This is a summarized view. Key sections extracted for efficiency.")

    result = "\n".join(output_parts)

    # Final size check
    if len(result) > _MAX_OUTPUT_SIZE:
        result = result[: _MAX_OUTPUT_SIZE - 50] + "\n\n... (truncated for context efficiency)"

    return result


class InnodbStatus(MySQLToolBase):
    name: str = "InnodbStatus"
    description: str = load_desc(Path(__file__).parent / "innodb_status.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW ENGINE INNODB STATUS with optimized output."""
        columns, rows = self._execute_query("SHOW ENGINE INNODB STATUS")

        if rows and len(rows[0]) > 2:
            raw_status = rows[0][2]  # The status text is in the third column

            # Parse and optimize output
            sections = _parse_innodb_sections(raw_status)

            if sections:
                optimized_output = _build_optimized_output(sections)
                return {
                    "data": optimized_output,
                    "message": (
                        f"InnoDB status retrieved ({len(sections)} sections parsed, optimized for context efficiency)"
                    ),
                }
            else:
                # Fallback: if parsing fails, truncate raw output
                truncated = raw_status[:_MAX_OUTPUT_SIZE] if len(raw_status) > _MAX_OUTPUT_SIZE else raw_status
                return {"data": truncated, "message": "InnoDB status retrieved (raw, parsing failed)"}
        else:
            return {"error": "No InnoDB status found", "brief": "No InnoDB status found"}
