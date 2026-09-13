# Authentication

Backend-only authentication using Google OAuth and JWT sessions. Password
authentication is out of scope.

## Google OAuth

- The backend owns the OAuth callback and validates `state`, `nonce`, PKCE,
  the authorization code, and the Google ID token.
- Match accounts by Google's stable `sub` value. Email is profile data only.
- The first registered user is atomically created as an enabled admin.
- Later users are created as pending guests.
- Pending and disabled users receive a restricted session so the API can return
  account status; they cannot access application APIs.

## Sessions

- Store access and refresh credentials in `HttpOnly`, `Secure`, `SameSite`
  cookies.
- Access JWT lifetime: 15 minutes.
- Refresh sessions are per device, server-tracked, revocable, and valid for
  30 days.
- Rotate refresh tokens on every use and revoke the session on reuse detection.
- Support current-session logout and revocation of all user sessions.
- Disabling an account or app revokes affected sessions immediately.

## Errors and security

- Return `401` for missing, invalid, expired, or revoked authentication.
- Return `403` with a stable machine-readable code for pending, disabled, or
  unauthorized accounts.
- Do not reveal account existence through public authentication errors.
- Require HTTPS, CSRF protection, an allowlisted CORS policy, rate limiting,
  managed secrets, and redacted logs.
