from __future__ import annotations

import re
from pathlib import Path


def main() -> None:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    if not config_path.exists():
        print("MISSING_CONFIG_FILE")
        return

    lines = config_path.read_text(encoding="utf-8").splitlines()

    in_logicpower = False
    in_selectors = False
    selector_values: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()

        if stripped == 'name: "logicpower"' or stripped == "name: 'logicpower'":
            in_logicpower = True
            in_selectors = False
            continue

        if in_logicpower and stripped.startswith("name:") and "logicpower" not in stripped:
            in_logicpower = False
            in_selectors = False

        if in_logicpower and stripped == "selectors:":
            in_selectors = True
            continue

        if in_selectors and stripped and not line.startswith("      "):
            in_selectors = False

        if in_selectors and ":" in stripped:
            key, value = stripped.split(":", 1)
            selector_values[key.strip()] = value.strip().strip("\"'")

    has_required_selectors = all(selector_values.get(k) for k in ("product_card", "title", "price", "product_url"))

    if has_required_selectors:
        print("SELECTORS_PRESENT")
        return

    raw = "\n".join(lines)
    has_non_empty_gemini_key = False
    if "gemini:" in raw:
        section = raw.split("gemini:", 1)[1]
        if "google_sheets:" in section:
            section = section.split("google_sheets:", 1)[0]
        has_non_empty_gemini_key = bool(
            re.search(r'(?m)^\s*-\s*"(?!\s*")[^"]+"\s*$', section)
            or re.search(r"(?m)^\s*-\s*'(?!\s*')[^']+'\s*$", section)
            or "AIza" in section
        )

    if has_non_empty_gemini_key:
        print("AUTO_DETECT_READY")
    else:
        print("MISSING_GEMINI_KEY")


if __name__ == "__main__":
    main()
