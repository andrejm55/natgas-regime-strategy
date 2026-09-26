from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.workflow import persist_feature_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_outright.yaml")
    args = parser.parse_args()
    db_path = persist_feature_table(args.config)
    print(f"Wrote feature table to {db_path}")


if __name__ == "__main__":
    main()
