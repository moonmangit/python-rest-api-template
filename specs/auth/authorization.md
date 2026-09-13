# Authorization

Authorization is enforced in the backend on every protected request.

## Roles

- `guest`: may view account status and log out only.
- `member`: may use applications only when explicitly granted access.
- `admin`: may manage members and automatically has spending-ledger access.

Guest is a real restricted role. Approval changes a pending guest to member;
an admin may also demote a member to guest. Demotion retains the member's data
but locks it from access.

## Application access

- Store access grants per user and application.
- A disabled spending-ledger grant blocks all ledger reads and writes.
- Account status and application grants are checked against current database
  state, not trusted solely from JWT claims.
- Every resource query is scoped to its owner. Cross-owner resources return
  `404` without disclosure.

## Admin operations

Admins may:

- list and search users;
- approve guests and change roles;
- enable or disable accounts and application grants;
- revoke user sessions; and
- view security and data-change audit entries.

The system must never leave zero enabled administrators. Self-demotion or
self-disable is rejected when it would violate this rule.

## Audit

Audit sign-in outcomes, role/status/access changes, session revocation,
account deletion, and ledger create/update/delete actions with actor, target,
action, and timestamp. Retain redacted audit entries after account deletion.

Protected endpoints use documented `401`, `403`, `404`, `409`, and `422`
responses with stable error codes.
