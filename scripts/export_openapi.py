from __future__ import annotations

import json
from pathlib import Path

from reservas_api.api.app import create_app


def main() -> None:
    """Export OpenAPI spec from FastAPI app into `docs/openapi.json`."""
    app = create_app()
    spec = app.openapi()
    output = Path("docs/openapi.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI exported to {output}")


if __name__ == "__main__":
    main()
