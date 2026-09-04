---
name: deploy-check
description: Run a read-only pre-deployment review for the single-client repository without deploying.
disable-model-invocation: true
---

Run the repository's documented release checks, inspect pending migrations and configuration names, verify the removed-scope CI gate, and summarize what would ship. Do not deploy, push, reset data, or apply production migrations.
