from __future__ import annotations

import pandas as pd


def london_newyork_session_mask(times: pd.Series) -> pd.Series:
    """Return True for London and New York core trading windows in UTC.

    London core: 07:00-11:59 UTC
    New York core: 13:00-17:59 UTC
    """
    hours = pd.to_datetime(times, utc=True).dt.hour
    london = (hours >= 7) & (hours <= 11)
    new_york = (hours >= 13) & (hours <= 17)
    return london | new_york
