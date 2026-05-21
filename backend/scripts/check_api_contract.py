"""检查 OpenAPI schema 与前端 TypeScript types 的一致性。"""

import json
import re
import sys
from pathlib import Path

OPENAPI_PATH = Path(__file__).parent.parent.parent / "docs" / "06-发布与运维" / "openapi.json"
TYPES_DIR = Path(__file__).parent.parent.parent / "frontend" / "src" / "app" / "types"


def load_openapi_schemas() -> dict[str, dict]:
    """从 OpenAPI JSON 提取所有 schema 定义。"""
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        spec = json.load(f)
    return spec.get("components", {}).get("schemas", {})


def extract_ts_interfaces() -> dict[str, set[str]]:
    """从 TypeScript 文件提取接口字段名。"""
    interfaces: dict[str, set[str]] = {}
    for ts_file in TYPES_DIR.glob("*.ts"):
        content = ts_file.read_text(encoding="utf-8")
        for match in re.finditer(
            r"(?:interface|type)\s+(\w+)\s*(?:=\s*\{)?\s*\n((?:\s+\w+.*\n)*)",
            content,
        ):
            name = match.group(1)
            body = match.group(2)
            fields = set()
            for line in body.strip().split("\n"):
                line = line.strip().rstrip(";,")
                if line and not line.startswith("//") and not line.startswith("*"):
                    field_match = re.match(r"(\w+)\??\s*:", line)
                    if field_match:
                        fields.add(field_match.group(1))
            if fields:
                interfaces[name] = fields
    return interfaces


def to_camel(snake: str) -> str:
    """snake_case 转 camelCase。"""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def check_consistency() -> list[str]:
    """对比 OpenAPI schema 与 TS 接口，返回差异列表。"""
    openapi_schemas = load_openapi_schemas()
    ts_interfaces = extract_ts_interfaces()
    differences = []

    for schema_name, schema_def in openapi_schemas.items():
        if schema_name not in ts_interfaces:
            continue

        schema_props = set(schema_def.get("properties", {}).keys())
        ts_fields = ts_interfaces[schema_name]

        schema_props_camel = {to_camel(p) for p in schema_props}

        missing_in_ts = schema_props_camel - ts_fields
        extra_in_ts = ts_fields - schema_props_camel

        if missing_in_ts:
            differences.append(f"{schema_name}: TS 缺少字段 {missing_in_ts}")
        if extra_in_ts:
            differences.append(f"{schema_name}: TS 多余字段 {extra_in_ts}")

    return differences


def main():
    if not OPENAPI_PATH.exists():
        print(f"ERROR: OpenAPI file not found at {OPENAPI_PATH}")
        sys.exit(1)

    if not TYPES_DIR.exists():
        print(f"ERROR: Types directory not found at {TYPES_DIR}")
        sys.exit(1)

    differences = check_consistency()

    if differences:
        print(f"Found {len(differences)} difference(s):")
        for diff in differences:
            print(f"  - {diff}")
        sys.exit(1)
    else:
        print("OK: OpenAPI schema and TypeScript types are consistent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
