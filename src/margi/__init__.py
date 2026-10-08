"""margi: AI in the margins, never in the text."""

from importlib.metadata import PackageNotFoundError, version

# pyproject.toml is the single source of the version.
try:
    __version__ = version("margi")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"
