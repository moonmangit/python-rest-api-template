# Spending Ledger

Backend API for a private per-member income and expense ledger.

## Data

- Every category, record, and attachment has an owner and is inaccessible to
  other users.
- Categories support one category level and one subcategory level.
- Category fields: name, parent, income/expense applicability, sort order,
  archived flag, and timestamps.
- Record fields: type (`income` or `expense`), positive integer
  `amount_minor`, `currency_code`, user-local calendar `date`, category,
  optional note, and timestamps.
- MVP supports USD only. Store currency per record for future currencies.
- User timezone defaults to UTC.

## Categories

- Owners can create, rename, reorder, archive, and restore categories.
- Names are unique per owner within the same parent and type scope.
- Archiving a parent archives its subcategories.
- Archived categories cannot be assigned to new or changed records but remain
  valid on historical records.

## Records

- Create, read, update, and hard-delete owned records.
- Create requires type, positive amount, date, and active category.
- Note maximum: 5,000 characters.
- Create supports an idempotency key; retries return the original result.
- Full updates may change type, amount, date, category, note, and attachments.
- Record changes are auditable.

## Attachments

- Store attachment metadata in PostgreSQL: owner, record, storage key, content
  type, byte size, checksum, and timestamps.
- Store image bytes in private file storage under a generated storage key. The
  MVP uses a persistent `UPLOAD_DIR`; production must use durable private
  object storage or an equivalent persistent volume.
- Allow up to 3 private JPEG, PNG, or WebP images per record.
- Maximum size is 10 MB per image.
- Validate MIME type and file signature; reject unsupported or unsafe files.
- Never expose the storage path or original filename as a public URL. Download
  requires ownership authorization and streams the file through the API.
- Replacing or removing an attachment deletes the old file only after the new
  state is safely stored.
- Failed database/file operations must not leave inaccessible orphan files.

## Reports

- Filter by category, subcategory, date range, type, and currency.
- Parent-category filters include all subcategories.
- Date ranges are inclusive and limited to 12 months. Default: current
  calendar month in the user's timezone.
- Return income total, expense total, net (`income - expense`), record count,
  category/subcategory breakdowns, and daily or monthly time series.
- Include zero-value buckets in the requested time-series range.
- Return records with deterministic cursor pagination, newest date first.

## API rules

- Validate ownership, category state, amounts, dates, currency, notes, and
  attachments on every write.
- Use stable machine-readable error codes with `401`, `403`, `404`, `409`, and
  `422` responses.
- Apply the authorization and audit rules defined in the auth specs.
