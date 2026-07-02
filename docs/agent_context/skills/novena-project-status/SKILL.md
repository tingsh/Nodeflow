---
name: novena-project-status
description: Use for Novena Hub or Novena Gateway work when Codex needs current project phase, sprint goal, recent activity, release readiness, or session wrap-up logging. Also use before ending a Novena session to update the project status reference.
---

# Novena Project Status

Read references/project_status.md at the start of substantial Novena work to understand where the project stands. The readable source lives under docs/agent_context/skills/novena-project-status, while .agents/skills/novena-project-status is a symlink for Codex discovery.

When completing a feature, bug fix, review, migration, or environment change:

1. Add a new dated entry to the top of the Recent Activity Log in references/project_status.md.
2. Mention concrete files, services, or workflows changed only when useful for the next agent.
3. Include validation results and any known blockers.
4. Keep the current phase and sprint goal accurate when work changes project direction.

Do not update the archived Antigravity files. They are historical only.
