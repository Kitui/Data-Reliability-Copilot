"""Backward-compatible facade for the modular profiling engine."""
from app.profiling import infer_column_type, profile_dataset

__all__ = ["infer_column_type", "profile_dataset"]
