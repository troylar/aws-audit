"""Resource name normalization for intelligent matching."""

from .config import NormalizerConfig
from .normalizer import NormalizationResult, ResourceNormalizer

__all__ = ["ResourceNormalizer", "NormalizationResult", "NormalizerConfig"]
