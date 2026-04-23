"""Minimal lap / sector view (run: ``pip install streamlit`` then ``streamlit run interfaces/ui/streamlit_app.py``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as script: add project root
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="DIL Race Engineer", layout="wide")
    st.title("Driver-in-the-Loop — lap snapshot")

    human_path = st.text_input("Human telemetry JSON", "data/sessions/human.json")
    opt_path = st.text_input("Optimal telemetry JSON", "data/sessions/optimal.json")

    if st.button("Load & compare"):
        hp = Path(human_path)
        op = Path(opt_path)
        if not hp.is_file() or not op.is_file():
            st.error("Paths must exist.")
            return
        human = json.loads(hp.read_text(encoding="utf-8"))
        opt = json.loads(op.read_text(encoding="utf-8"))
        if isinstance(human, dict) and "telemetry" in human:
            human = human["telemetry"]
        if isinstance(opt, dict) and "telemetry" in opt:
            opt = opt["telemetry"]
        h_t = human[-1]["time"] if human else 0.0
        o_t = opt[-1]["time"] if opt else 0.0
        st.metric("Human lap (s)", f"{h_t:.2f}")
        st.metric("Optimal lap (s)", f"{o_t:.2f}")
        st.metric("Delta (s)", f"{h_t - o_t:+.2f}")

        st.subheader("Human telemetry (preview)")
        if human:
            st.dataframe(human[: min(2000, len(human))])


if __name__ == "__main__":
    main()
