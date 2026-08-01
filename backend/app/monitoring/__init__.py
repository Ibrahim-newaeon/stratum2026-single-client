# =============================================================================
# ADs Growth System - Memory Monitoring Package
# =============================================================================
"""
Full memory audit system for ADs Growth System platform.

Components:
- MemoryAuditor: Core engine (tracemalloc, psutil, gc, objgraph)
- MemoryProfilingMiddleware: Per-endpoint memory tracking
- CeleryMemoryHooks: Per-task memory tracking
- ReportGenerator: HTML reports with embedded visualizations
"""

from app.monitoring.memory_audit import MemoryAuditor

__all__ = ["MemoryAuditor"]
