"""VIStk.Bindings — state-management primitives for dict-backed UIs.

This namespace is intended to grow. RecordBinding (single-record editor
support) lands first; ListBinding (collection editor support) is planned
as a separate v1 in its own tracker.
"""

from VIStk.Bindings._RecordBinding import RecordBinding

__all__ = ["RecordBinding"]
