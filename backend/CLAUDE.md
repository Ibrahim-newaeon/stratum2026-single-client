# Stratum Single-Client Backend Guide

Follow the root guide, `.claude/rules/single-client-boundary.md`, and `.claude/rules/backend.md`.

This directory owns FastAPI routes, services, models, Alembic migrations, Celery jobs, integrations, trust-gate enforcement, and backend tests. Do not introduce tenant scope, subscriptions, licensing, Stripe, Paddle, or any payment-processing path.

Preserve authentication, roles, auditability, idempotency, async I/O, and transaction ownership. Use the root Makefile or backend-declared commands and run focused tests before the broader affected gate.
