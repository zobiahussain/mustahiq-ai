# services/api - FastAPI Backend

FastAPI + Pydantic v2 layer serving both apps. It owns the shared database connection layer and the staff portal routes under `/portal`.

The public support chatbot uses `/portal/support/programs` and `/portal/support/chat`. Those endpoints expose only active program descriptions and saved program/source passages, not beneficiary or staff casework data.

## Staff Auth

Staff portal live mode uses Supabase Auth email/password. The `staff_users.auth_user_id` column must map each app staff row to a Supabase Auth user. `area_manager`, `department_admin`, and `super_admin` roles gate program editing and department visibility.

Local `PORTAL_DEMO_MODE=true` exposes a clearly labelled synthetic demo session and stores data in SQLite.

## Marketplace

The marketplace remains a separate beneficiary-facing module. Its standalone API entry point is `services/api/main.py`; `services/api/unified.py` can mount marketplace and staff apps together for integration work.

## Setup

For staff portal setup, migration notes, and verification commands, see `docs/Staff_Portal_Integration.md`.
