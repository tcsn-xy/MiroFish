"""
Simulation profile file helpers.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List


PROFILE_FILES = {
    "reddit": "reddit_profiles.json",
    "twitter": "twitter_profiles.csv",
}


def get_profile_file_path(sim_dir: str, platform: str) -> str:
    """Return the expected profile file path for a platform."""
    try:
        filename = PROFILE_FILES[platform]
    except KeyError as exc:
        raise ValueError(f"Unsupported platform: {platform}") from exc
    return os.path.join(sim_dir, filename)


def load_profiles(sim_dir: str, platform: str) -> List[Dict[str, Any]]:
    """Load simulation profiles for the given platform."""
    profile_path = get_profile_file_path(sim_dir, platform)
    if not os.path.exists(profile_path):
        return []

    if platform == "twitter":
        with open(profile_path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def count_profiles(sim_dir: str, platform: str) -> int:
    """Return the number of stored profiles for the given platform."""
    return len(load_profiles(sim_dir, platform))
