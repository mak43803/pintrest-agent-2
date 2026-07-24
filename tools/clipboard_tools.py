"""
Clipboard Tools — OS Clipboard interactions.
=============================================

Provides methods to copy, paste, and clear the system clipboard.
Uses native Windows commands (clip, Get-Clipboard) to avoid needing
external dependencies like pyperclip.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("pinterest_agent.tools.clipboard")


class ClipboardTools:
    """Operations for interacting with the system clipboard."""

    @staticmethod
    def copy(text: str) -> None:
        """
        Copy text to the clipboard.
        
        Uses the Windows ``clip`` command.
        """
        try:
            # We encode the text to bytes and pipe it to clip.exe
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            process.communicate(input=text.encode("utf-16le"))
            logger.debug("Text copied to clipboard.")
        except Exception as exc:
            logger.error("Failed to copy to clipboard: %s", exc)
            raise

    @staticmethod
    def paste() -> str:
        """
        Paste text from the clipboard.
        
        Uses PowerShell's ``Get-Clipboard`` command.
        """
        try:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                check=True
            )
            # Remove trailing newline added by powershell
            text = result.stdout.rstrip("\\n").rstrip("\\r")
            logger.debug("Text pasted from clipboard.")
            return text
        except Exception as exc:
            logger.error("Failed to paste from clipboard: %s", exc)
            raise

    @staticmethod
    def clear() -> None:
        """
        Clear the clipboard.
        
        Pipes an empty string into clip.exe.
        """
        try:
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Pipe empty string
            process.communicate(input=b"")
            logger.debug("Clipboard cleared.")
        except Exception as exc:
            logger.error("Failed to clear clipboard: %s", exc)
            raise
