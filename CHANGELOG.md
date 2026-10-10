# Changelog

## Unreleased

### Added

- Infer compact 14-digit timestamps such as `20140111132105` as `%Y%m%d%H%M%S`.

## 0.4.0 - 2026-08-25

### Added

- Infer compact year-first dates such as `20130814` as `%Y%m%d`.
- Infer fractional seconds with one to six digits as `%f`.
- Recognize ISO 8601 UTC offsets in compact, zero, and colon-delimited forms.
- Support custom rule elements consistently through the complete `DateElement`
  protocol.

### Changed

- Use modern `pyproject.toml` metadata and reproducible `uv`/hatchling builds for
  the `pydateinfer` distribution, with Python 3.10 or newer required.
- Reject an empty example collection with a clear `ValueError`.
- Treat an explicitly empty alternative rule list as disabling rewrites.

### Fixed

- Infer year-first numeric dates correctly.
- Infer numeric days beside textual months as `%d` instead of an hour.
- Make modal-value tie breaking independent of example order.
- Reject empty tokens as textual month names.
- Match overlapping rule sequences and inspect every element between `Next`
  rule operands.
- Avoid `SyntaxWarning` messages from rule wildcard strings on import.
