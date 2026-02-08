"""AWS Baseline Snapshot & Delta Tracking tool."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("aws-inventory-manager")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
