#!/usr/bin/env python3

import os
from pathlib import Path
import pathspec

def find_project_root(start_path):
    current_path = Path(start_path)
    
    while current_path != current_path.root:
        if (current_path / ".git").is_dir():
            return str(current_path)
        
        if (current_path / ".hg").is_dir():
            return current_path
        
        if (current_path / "pyproject.toml").is_file():
            return current_path
        
        if (current_path / "setup.py").is_file():
            return current_path
        
        current_path = current_path.parent
        
    return None

ALWAYS_IGNORE = """
.git
__pycache__
.direnv
.eggs
.git
.hg
.mypy_cache
.nox
.tox
.venv
venv
.svn
.ipynb_checkpoints
_build
buck-out
build
dist
__pypackages__
"""

def load_gitignore_spec_at_path(path):
    gitignore_path = os.path.join(path, ".gitignore")
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            patterns = f.read().split("\n")
            patterns.extend(ALWAYS_IGNORE.split("\n"))
        ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    else:
        ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", [])
    return ignore_spec