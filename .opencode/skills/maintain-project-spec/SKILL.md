---
name: maintain-project-spec
description: Maintain the project's concise backend requirements in specs/auth and specs/app without contradictions or scope bloat. Use when creating, reviewing, or changing authentication, authorization, or spending-ledger specifications.
---

# Maintain Project Spec

Use this skill only for backend requirement documents under `specs/`.

## Files

- `specs/main.md`: concise index and scope.
- `specs/auth/authentication.md`: Google OAuth and sessions.
- `specs/auth/authorization.md`: roles, access grants, ownership, and audit.
- `specs/app/spending_ledger.md`: ledger data, rules, attachments, and reports.

## Rules

- Write requirements, not implementation tutorials or frontend behavior.
- Prefer short bullets over explanatory paragraphs.
- Every requirement must be testable or define a necessary invariant.
- Do not invent endpoints, fields, workflows, or future features without a
  confirmed decision. Mark deferred work as `planned` or `out of scope`.
- Keep each rule in its owning document. Cross-reference instead of duplicating
  it.
- Remove repeated or weaker wording when adding a more precise rule.
- Keep terminology and role names consistent across all three files.

## Current Invariants

Authentication and authorization:

- Google OAuth uses a backend callback and Google's stable `sub` identifier.
- The first registered user is atomically an enabled admin.
- Later users are pending `guest` accounts with status-only access.
- `member` access requires an application grant.
- Enabled admins automatically access the spending ledger.
- Current account and application state is checked from the database.
- The last enabled admin cannot be removed or disabled.
- Access tokens last 15 minutes; rotating, revocable refresh sessions last 30
  days and use secure HTTP-only cookies.

Spending ledger:

- Data is private to its owner.
- Records support positive minor-unit `income` and `expense` amounts.
- MVP currency is USD; retain a per-record currency field for future support.
- Dates are user-local calendar dates; the default timezone is UTC.
- Categories have one category and one subcategory level and can be archived.
- Archived categories remain valid for history but cannot be newly assigned.
- Attachment metadata is stored in PostgreSQL; image bytes use private file
  storage with a persistent `UPLOAD_DIR` for MVP.
- Reports return income, expense, net, breakdowns, and zero-filled time series.

## Editing Workflow

1. Read all three files before changing a related requirement.
2. Identify the owning document and update the smallest necessary section.
3. Check role, access, ownership, currency, storage, deletion, and report rules
   for contradictions.
4. Delete duplication and keep the final wording backend-only.
5. Review the complete changed files for unnecessary detail and unresolved
   placeholders.
6. Run `just check` before completing the change.

If a requirement is materially ambiguous, ask one focused question instead of
choosing silently.

API implementation changes are separate from spec maintenance: when an API
contract is implemented or changed, update the root `bruno/` collection too.
