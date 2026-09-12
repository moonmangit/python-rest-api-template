# Project Instructions

- Read `.agents/skills/project-conventions/SKILL.md` before changing project code.
- Organize business code by bounded context under `app/features/<feature>/`.
- Every business feature must contain `domain/`, `application/`, and `presentation/` boundaries, even when the feature is small.
- Keep domain rules out of presentation and keep HTTP concerns out of domain/application code.
- Put cross-feature infrastructure in `app/core/` or `app/shared/` only when it is genuinely shared.
- Update the root-level `bruno/` collection whenever an API contract changes.
- Run `just check` before completing a change.
