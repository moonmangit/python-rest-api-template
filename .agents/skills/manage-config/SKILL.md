---
name: manage-config
description: Manage environment-backed application settings without leaking secrets or coupling configuration to routes.
---

# Manage Configuration

Use this skill for application settings, environment variables, and local configuration.

- Keep settings in `app/core/config.py` using `pydantic-settings`.
- Add typed settings with safe development defaults and load overrides from environment variables or `.env`.
- Keep `.env` out of source control; document new variables in `.env.example`.
- Do not read environment variables directly in routes, models, or services.
- Do not commit passwords, tokens, production URLs, or other secrets.
- Keep configuration changes backward-compatible for the local Compose workflow unless the task explicitly changes it.
- Validate settings at application import or startup and test important environment overrides.
