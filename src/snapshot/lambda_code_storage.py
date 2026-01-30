"""External storage for Lambda deployment packages.

Stores large Lambda code packages to disk instead of inline in snapshots.
"""

import base64
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class LambdaCodeStorage:
    """Manages external storage of Lambda deployment packages."""

    def __init__(self, base_path: Optional[str] = None):
        """Initialize Lambda code storage.

        Args:
            base_path: Base directory for storing Lambda code.
                      Defaults to ~/.snapshots/lambda-code/
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.home() / ".snapshots" / "lambda-code"

    def get_snapshot_code_dir(self, snapshot_name: str) -> Path:
        """Get the directory for a snapshot's Lambda code.

        Args:
            snapshot_name: Name of the snapshot

        Returns:
            Path to the snapshot's code directory
        """
        return self.base_path / snapshot_name

    def store_code(
        self,
        snapshot_name: str,
        function_name: str,
        code_bytes: bytes,
    ) -> Tuple[str, str]:
        """Store Lambda code to external file.

        Args:
            snapshot_name: Name of the snapshot
            function_name: Name of the Lambda function
            code_bytes: Raw bytes of the deployment package (zip)

        Returns:
            Tuple of (file_path, sha256_hash)
        """
        # Create directory structure
        code_dir = self.get_snapshot_code_dir(snapshot_name)
        code_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize function name for filesystem
        safe_name = self._sanitize_filename(function_name)
        file_path = code_dir / f"{safe_name}.zip"

        # Compute hash
        code_hash = hashlib.sha256(code_bytes).hexdigest()

        # Write the file
        with open(file_path, "wb") as f:
            f.write(code_bytes)

        logger.debug(f"Stored Lambda code for {function_name} to {file_path} ({len(code_bytes)} bytes)")

        return str(file_path), code_hash

    def load_code(self, file_path: str) -> Optional[bytes]:
        """Load Lambda code from external file.

        Args:
            file_path: Path to the code file

        Returns:
            Raw bytes of the deployment package, or None if file not found
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Lambda code file not found: {file_path}")
            return None

        with open(path, "rb") as f:
            return f.read()

    def load_code_base64(self, file_path: str) -> Optional[str]:
        """Load Lambda code from external file as base64.

        Args:
            file_path: Path to the code file

        Returns:
            Base64-encoded code, or None if file not found
        """
        code_bytes = self.load_code(file_path)
        if code_bytes:
            return base64.b64encode(code_bytes).decode("utf-8")
        return None

    def delete_snapshot_code(self, snapshot_name: str) -> bool:
        """Delete all code files for a snapshot.

        Args:
            snapshot_name: Name of the snapshot

        Returns:
            True if deleted, False if not found
        """
        code_dir = self.get_snapshot_code_dir(snapshot_name)
        if code_dir.exists():
            shutil.rmtree(code_dir)
            logger.debug(f"Deleted Lambda code directory for snapshot: {snapshot_name}")
            return True
        return False

    def get_code_size(self, file_path: str) -> Optional[int]:
        """Get the size of a stored code file.

        Args:
            file_path: Path to the code file

        Returns:
            File size in bytes, or None if not found
        """
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size
        return None

    def list_snapshot_code_files(self, snapshot_name: str) -> list:
        """List all code files for a snapshot.

        Args:
            snapshot_name: Name of the snapshot

        Returns:
            List of file paths
        """
        code_dir = self.get_snapshot_code_dir(snapshot_name)
        if not code_dir.exists():
            return []

        return [str(f) for f in code_dir.glob("*.zip")]

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename.

        Args:
            name: Original name

        Returns:
            Safe filename string
        """
        # Replace problematic characters
        safe = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        safe = safe.replace("<", "_").replace(">", "_").replace("|", "_")
        safe = safe.replace("*", "_").replace("?", "_").replace('"', "_")
        return safe
