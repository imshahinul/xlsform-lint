"""Stable, source-oriented plain-text diagnostic rendering."""

from __future__ import annotations

from typing import Iterable

from .diagnostics import Diagnostic, SourceLocation, sort_diagnostics, summarize


def render_source(source: SourceLocation) -> str:
    """Render only source components that are actually available."""

    parts: list[str] = [source.path]
    if source.sheet is not None:
        parts.append(source.sheet)
    if source.row is not None:
        parts.append(str(source.row))
    if source.column is not None:
        parts.append(source.column)
    elif source.cell is not None:
        parts.append(source.cell)
    return ":".join(parts)


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def format_diagnostics(diagnostics: Iterable[Diagnostic]) -> str:
    """Render deterministically ordered findings and the stable V1 summary."""

    ordered = sort_diagnostics(diagnostics)
    blocks: list[str] = []
    for diagnostic in ordered:
        lines = []
        if diagnostic.source is not None:
            lines.append(render_source(diagnostic.source))
        lines.append(
            f"{diagnostic.rule_id} {diagnostic.severity} {diagnostic.message}"
        )
        if diagnostic.help is not None:
            lines.append(f"help: {diagnostic.help}")
        blocks.append("\n".join(lines))

    summary = summarize(ordered)
    summary_text = (
        f"{summary.errors} {_plural(summary.errors, 'error')}, "
        f"{summary.warnings} {_plural(summary.warnings, 'warning')}"
    )
    return "\n\n".join((*blocks, summary_text)) + "\n"
