#!/usr/bin/env python3

"""Flatten SQL metric definitions from metrics.yaml into plain folders and files
for faster grep access

Example:
    metrics.archiver.sqls.14 -> flattened_metrics/archiver/14/archiver_metric_14.sql

Copilot generated
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install it with: pip install pyyaml"
    ) from exc


def sanitize_segment(segment: str) -> str:
    """Keep filesystem-safe path segments."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(segment))
    return cleaned or "_"


def leaf_filename(path_parts: list[str], value: Any) -> str:
    """Choose a file name for a leaf value."""
    last = path_parts[-1]
    parent = path_parts[-2] if len(path_parts) > 1 else ""

    if last == "sql" or (parent == "sqls" and last.isdigit()):
        return "metrics.sql"
    if last == "init_sql":
        return "init.sql"

    stem = sanitize_segment(last)
    ext = ".txt" if isinstance(value, str) else ".yaml"
    return f"{stem}{ext}"


def serialize_value(value: Any) -> str:
    if isinstance(value, str):
        return value if value.endswith("\n") else value + "\n"
    dumped = yaml.safe_dump(value, sort_keys=False, default_flow_style=False)
    return dumped if dumped.endswith("\n") else dumped + "\n"


def ensure_sql_ending(content: str) -> str:
    trimmed = content.rstrip()
    if not trimmed.endswith(";"):
        trimmed += ";"
    return trimmed + "\n"


def sql_output_filename(
    metric_name: str,
    node_status: str | None,
    version_key: str | None = None,
) -> str:
    metric_stem = sanitize_segment(metric_name)
    parts = [f"{metric_stem}_metric"]

    if version_key:
        parts.append(sanitize_segment(version_key))

    if node_status:
        parts.append(sanitize_segment(node_status))

    return "_".join(parts) + ".sql"


def write_sql_leaf(
    output_root: Path,
    metric_name: str,
    sql_key: str,
    sql_value: Any,
    node_status: str | None,
) -> None:
    path_parts = ["metrics", metric_name, sql_key]
    write_leaf(
        output_root,
        path_parts,
        sql_value,
        output_filename=sql_output_filename(metric_name, node_status),
    )


def write_sqls_leaf(
    output_root: Path,
    metric_name: str,
    pg_version: str,
    sql_value: Any,
    node_status: str | None,
) -> None:
    path_parts = ["metrics", metric_name, "sqls", str(pg_version)]
    write_leaf(
        output_root,
        path_parts,
        sql_value,
        output_filename=sql_output_filename(metric_name, node_status, pg_version),
    )


def extract_sql_metrics(metrics_root: dict[str, Any], output_root: Path) -> None:
    """Extract only sql/sqls keys for each metric and ignore all other keys."""
    for metric_name, metric_def in metrics_root.items():
        if not isinstance(metric_def, dict):
            continue

        node_status = metric_def.get("node_status")
        if not isinstance(node_status, str):
            node_status = None

        if "sql" in metric_def:
            write_sql_leaf(
                output_root,
                str(metric_name),
                "sql",
                metric_def["sql"],
                node_status,
            )

        sqls = metric_def.get("sqls")
        if isinstance(sqls, dict):
            for pg_version, sql_value in sqls.items():
                write_sqls_leaf(
                    output_root,
                    str(metric_name),
                    str(pg_version),
                    sql_value,
                    node_status,
                )


def write_leaf(
    output_root: Path,
    path_parts: list[str],
    value: Any,
    output_filename: str | None = None,
) -> None:
    rel_parts = path_parts[:-1]

    # Flatten .../sqls/<version> so version folders live directly under metric name.
    if len(path_parts) >= 2 and path_parts[-2] == "sqls" and path_parts[-1].isdigit():
        rel_parts = path_parts[:-2] + [path_parts[-1]]

    rel_dir = [sanitize_segment(p) for p in rel_parts]
    out_dir = output_root.joinpath(*rel_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / (output_filename or leaf_filename(path_parts, value))
    content = serialize_value(value)
    if out_file.suffix == ".sql":
        content = ensure_sql_ending(content)
    out_file.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract only SQL metric keys (sql/sqls) to folders/files"
    )
    parser.add_argument(
        "--input",
        default="metrics.yaml",
        help="Path to source YAML (default: metrics.yaml)",
    )
    parser.add_argument(
        "--output",
        default="flattened_metrics",
        help="Output root folder (default: flattened_metrics)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output)

    data = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "metrics" not in data:
        raise SystemExit("Input YAML does not contain a top-level 'metrics' key")

    metrics_root = data["metrics"]
    if not isinstance(metrics_root, dict):
        raise SystemExit("Top-level 'metrics' is not a mapping")

    extract_sql_metrics(metrics_root, output_root)


if __name__ == "__main__":
    main()
