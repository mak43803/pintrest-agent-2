"""
File Tools — High-level file system operations for the agent.
==============================================================

Provides a clean, unified API for common file operations.
Used by the ToolManager to allow the agent to manage its workspace.

Features:
    • Read / Write text files
    • Delete, Move, Copy, Rename files
    • Create directories
    • Graceful exception handling
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("pinterest_agent.tools.file")


class FileTools:
    """Operations for reading, writing, and managing files."""

    @staticmethod
    def read_file(filepath: str | Path) -> str:
        """Read the entire contents of a file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
            
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_file(filepath: str | Path, content: str, append: bool = False) -> None:
        """Write content to a file. Creates parent directories if missing."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
            
        logger.debug("File written  │  path=%s  mode=%s", path.name, mode)

    @staticmethod
    def delete_file(filepath: str | Path) -> None:
        """Delete a file or directory."""
        path = Path(filepath)
        if not path.exists():
            return
            
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
            
        logger.debug("File deleted  │  path=%s", path.name)

    @staticmethod
    def move_file(src: str | Path, dst: str | Path) -> None:
        """Move a file to a new location."""
        src_path, dst_path = Path(src), Path(dst)
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src_path}")
            
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        logger.debug("File moved  │  src=%s  dst=%s", src_path.name, dst_path.name)

    @staticmethod
    def copy_file(src: str | Path, dst: str | Path) -> None:
        """Copy a file or directory to a new location."""
        src_path, dst_path = Path(src), Path(dst)
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src_path}")
            
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            shutil.copy2(src_path, dst_path)
            
        logger.debug("File copied  │  src=%s  dst=%s", src_path.name, dst_path.name)

    @staticmethod
    def rename_file(src: str | Path, new_name: str) -> None:
        """Rename a file in the same directory."""
        src_path = Path(src)
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src_path}")
            
        dst_path = src_path.with_name(new_name)
        src_path.rename(dst_path)
        logger.debug("File renamed  │  old=%s  new=%s", src_path.name, new_name)

    @staticmethod
    def create_folder(dirpath: str | Path) -> None:
        """Create a directory and any missing parents."""
        path = Path(dirpath)
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Folder created  │  path=%s", path.name)
