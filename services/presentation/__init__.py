"""Public read-model projection services for Saudi Defense Atlas.

This package is included in the exact-head M1 acceptance verification gate.
"""

from .equipment_view import ProjectionError, build_equipment_view

__all__ = ["ProjectionError", "build_equipment_view"]
