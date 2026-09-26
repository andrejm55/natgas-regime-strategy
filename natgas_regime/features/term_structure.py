from __future__ import annotations
import pandas as pd

def add_term_structure(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["spread_settle"] = out["ng1_settle"] - out["ng2_settle"]
    out["slope"] = (out["ng2_settle"] - out["ng1_settle"]) / out["ng1_settle"]
    out["curve_regime"] = out["slope"].map(lambda x: "backwardation" if x < 0 else "contango")
    return out
