---
name: manage-bruno
description: Keep the root-level Bruno API collection synchronized with this FastAPI application's current routes.
---

# Manage Bruno

Use this skill whenever an API route, request body, response, or public URL changes.

- Store the collection at `bruno/` in the project root.
- Keep collection metadata in `bruno/bruno.json` and local variables in `bruno/environments/local.bru`.
- Use `{{baseUrl}}` for the host; the local default is `http://127.0.0.1:3001`.
- Organize requests by resource, with a `root/` folder for the root endpoint.
- Create one `.bru` request per meaningful HTTP operation, including method, URL, auth, and body mode.
- Include representative JSON in `body:json` for POST or other write requests.
- Reflect route prefixes and trailing slashes exactly as defined by FastAPI.
- When an endpoint is removed, remove its Bruno request in the same change.
- Check Bruno coverage against `app.openapi()['paths']`; use the Bruno CLI for execution when it is installed.
