---
name: test-flow
description: Verify an affected single-client backend or frontend flow with focused checks and the relevant broader gate.
---

Map the changed behavior to focused unit, integration, and UI tests. Include authorization, failure, stale-data, and duplicate-action cases where relevant. Run the smallest useful checks first, then the affected broader gate, and report exact results without claiming unrun checks.
