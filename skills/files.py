"""
============================================================
J.A.R.V.I.S. — File & Folder Operations Skill
Layer 3 / Phase 2: FR-18 File Operations
============================================================
Handles: open files, open folders, search files, create folders
"""

import os
import glob
import logging
import subprocess
from pathlib import Path
from fuzzywuzzy import fuzz

from core.brain import Intent, Response
from config import Config

log = logging.getLogger("jarvis.skills.files")

# Common folders map
FOLDER_MAP = {
    "desktop": str(Path.home() / "Desktop"),
    "downloads": str(Path.home() / "Downloads"),
    "documents": str(Path.home() / "Documents"),
    "pictures": str(Path.home() / "Pictures"),
    "music": str(Path.home() / "Music"),
    "videos": str(Path.home() / "Videos"),
    "c drive": "C:\\",
    "d drive": "D:\\",
}


def _open_path(path: str):
    """Open a file or folder in the default application / Explorer."""
    os.startfile(path)


def handle_file_search(intent: Intent) -> Response:
    query = intent.params.get("query", "").strip()
    location_str = intent.params.get("location", "documents").strip().lower()

    # Resolve location
    search_dir = FOLDER_MAP.get(location_str)
    if not search_dir:
        search_dir = str(Path.home() / "Documents")

    # Determine file extension filter
    ext_map = {
        "pdf": "*.pdf", "pdfs": "*.pdf",
        "word": "*.docx", "doc": "*.docx",
        "image": "*.jpg", "images": "*.jpg",
        "python": "*.py", "py": "*.py",
        "text": "*.txt", "txt": "*.txt",
        "excel": "*.xlsx", "spreadsheet": "*.xlsx",
    }
    pattern = ext_map.get(query.lower(), f"*{query}*")

    try:
        matches = glob.glob(str(Path(search_dir) / "**" / pattern), recursive=True)[:10]
        if not matches:
            return Response(
                text=f"No {query} files found in your {location_str} folder, Sir.",
                success=False
            )
        file_names = [Path(m).name for m in matches[:5]]
        file_list = ", ".join(file_names)
        return Response(
            text=f"Found {len(matches)} {query} file{'s' if len(matches) > 1 else ''} in {location_str}: {file_list}.",
            data={"files": matches}
        )
    except Exception as e:
        log.error("File search error: %s", e)
        return Response(text=f"File search failed, Sir: {e}", success=False)


def handle_folder_create(intent: Intent) -> Response:
    name = intent.params.get("name", "").strip()
    location_str = intent.params.get("location", "Desktop").strip().lower()

    location = FOLDER_MAP.get(location_str, str(Path.home() / "Desktop"))

    try:
        new_folder = Path(location) / name
        new_folder.mkdir(parents=True, exist_ok=True)
        _open_path(str(new_folder))
        return Response(text=f"Created folder '{name}' on your {location_str}, Sir.")
    except Exception as e:
        log.error("Folder creation error: %s", e)
        return Response(text=f"Couldn't create the folder, Sir: {e}", success=False)


def handle_open_folder(intent: Intent) -> Response:
    """Handle 'Open Downloads folder', 'Open Documents' etc."""
    app_name = intent.params.get("app_name", "").lower()

    # Check if it matches a known folder
    for key, path in FOLDER_MAP.items():
        if key in app_name or fuzz.partial_ratio(key, app_name) >= 80:
            try:
                _open_path(path)
                return Response(text=f"Opening your {key} folder, Sir.")
            except Exception as e:
                return Response(text=f"Couldn't open that folder, Sir: {e}", success=False)

    return None   # Signal to fall through to app launcher


def register(brain):
    """Register file operation skill handlers."""
    brain.register_skill("file_search", handle_file_search)
    brain.register_skill("folder_create", handle_folder_create)
