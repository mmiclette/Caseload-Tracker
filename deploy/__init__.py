"""
Hosting layer for the public prototype.

Everything in this package is additive: it wraps ``app/`` and
``frontend/dist`` for deployment and is imported by nothing the registry
itself depends on. Deleting this directory leaves the registry unchanged.
"""
