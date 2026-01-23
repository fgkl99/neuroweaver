import json
from pathlib import Path
import pandas as pd

from tools.feature_determinism import df_sha256, normalize_df

def test_hash_deterministic_for_same_df():
    df = pd.DataFrame({"b":[1.0,2.0], "a":[3.0,4.0]})
    h1 = df_sha256(df)
    h2 = df_sha256(df)
    assert h1 == h2
