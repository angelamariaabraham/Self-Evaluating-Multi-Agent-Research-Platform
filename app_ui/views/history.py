"""Tab 6: benchmark across past runs (runs.csv)."""
import pandas as pd
import streamlit as st

from ..components import STRETCH
from ..runs_io import RUNS_CSV


def render() -> None:
    if not RUNS_CSV.exists():
        st.info("No `runs.csv` found in workspace.")
        return
    try:
        df = pd.read_csv(RUNS_CSV)
    except (OSError, ValueError) as e:
        st.error(f"Error reading runs.csv: {e}")
        return

    st.dataframe(df, **STRETCH)
    if "faithfulness" in df.columns:
        st.markdown("**Faithfulness Rate Trend Across Past Runs:**")
        st.line_chart(df.dropna(subset=["faithfulness"])["faithfulness"])
