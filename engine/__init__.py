"""SUTRA resolution engine.

Layers 1 to 9. Runs as a local batch job, never inside a deployed function.
See docs/architecture.md section 2 for why the compute is split that way.

Phase 0 status. Only `policy` is implemented. The layer packages exist as
scaffold so the import paths are settled before code lands in them.
"""
