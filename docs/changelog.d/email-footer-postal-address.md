---
version: 2.20.363
type: fix
area: email
date: 2026-11-24
---
- Every email footer (daily digest, welcome, account and press mail, digest archive) now prints the business postal address "Ask The Recruiter, Torenlaan 5, 1402 AT Bussum, Netherlands." The old interim line carried no street, which CAN-SPAM requires. The address is the Postadres Nederland postal mailbox, public business address (owner ruling 2026-11-13). Removed the stale pending-owner-item marker from postal-address.json.
- Tests: test_postal_address.py pins the address and the removal of the marker; footer assertions in test_account_mail.py, test_press_list.py, test_digest_archive.py and the welcome snapshot updated.
