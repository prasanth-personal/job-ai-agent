from datetime import date
import pandas as pd
from collections import Counter


def export_skill_gaps(skill_gap_tracker: Counter, filename: str = None) -> str:
    """Saves the skill gap tracker to a date-stamped Excel file."""
    if filename is None:
        filename = f"skill_gaps_{date.today().isoformat()}.xlsx"

    if not skill_gap_tracker:
        print("No skill gap data to export.")
        return None

    df = pd.DataFrame(
        skill_gap_tracker.most_common(20),
        columns=["Skill", "Jobs Mentioning It"]
    )
    df.to_excel(filename, index=False)
    print(f"Exported skill gap report to {filename}")
    return filename