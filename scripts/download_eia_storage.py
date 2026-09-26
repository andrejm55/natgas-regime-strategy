from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.eia_storage import EIAStorageClient


def main() -> None:
    load_dotenv(".env")
    data_cfg = load_yaml("config/data.yaml")
    client = EIAStorageClient.from_config(data_cfg["eia"])
    frame = client.fetch()
    output_dir = resolve_path(data_cfg["eia"]["raw_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "eia_weekly_storage.csv"
    frame.to_csv(output_path, index=False)
    latest = frame.iloc[-1]
    print(
        f"Wrote {len(frame)} rows to {output_path}. "
        f"Latest week ending {latest['week_ending_date'].date()} = "
        f"{latest['storage_bcf']:.0f} Bcf."
    )


if __name__ == "__main__":
    main()

