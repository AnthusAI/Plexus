"""Isolated asynchronous score processor runtime distribution."""

from importlib.resources import files
from pathlib import Path


def dockerfile_path() -> Path:
    """Return the installed, self-contained runtime Dockerfile path."""
    resource = files(__package__).joinpath("Dockerfile")
    path = Path(str(resource))
    if not path.is_file():
        raise FileNotFoundError("Packaged async score processor Dockerfile is missing")
    return path


__all__ = ["dockerfile_path"]
