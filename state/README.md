# State Directory

This directory exists for local-only runtime state that should not be committed.

Expected local content:

- config backups under `state/backups/`
- scratch validation notes
- local-only troubleshooting artifacts

Do not place committed secrets here.
