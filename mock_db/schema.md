# Mock DB Schema

This folder contains JSON files that mimic relational tables.

## Tables

### `clients.json`
Primary table for client accounts.

Fields:
- `id` (string, PK): internal client/client id (example: `usr_001`)
- `enterprise_number` (string): company identifier
- `account_id` (string): account identifier used by API queries
- `first_name` (string)
- `last_name` (string)
- `email` (string)
- `phone` (string)
- `city` (string)
- `created_at` (string, ISO-8601 datetime)

### `invoices.json`
Invoice records linked to clients.

Fields:
- `id` (string, PK): invoice id (example: `inv_0001`)
- `client_id` (string, FK -> `clients.id`)
- `amount` (number): invoice amount
- `date_created` (string, `YYYY-MM-DD`)
- `date_paid` (string or `null`, `YYYY-MM-DD`)
- `is_paid` (boolean)

Rules:
- If `is_paid = true`, `date_paid` should be set.
- If `is_paid = false`, `date_paid` is typically `null`.

### `client_products.json`
Products/subscriptions owned by a client.

Fields:
- `id` (string, PK): link row id (example: `up_001`)
- `client_id` (string, FK -> `clients.id`)
- `product_id` (string): product identifier
- `product_name` (string)
- `start_date` (string, `YYYY-MM-DD`)
- `end_date` (string or `null`, `YYYY-MM-DD`)
- `is_active` (boolean)

### `client_employees.json`
Employees working at a client company.

Fields:
- `id` (string, PK): employee record id (example: `emp_001`)
- `client_id` (string, FK -> `clients.id`)
- `first_name` (string)
- `last_name` (string)
- `email` (string)
- `role` (string)
- `department` (string)
- `monthly_income` (number): monthly income for this employee
- `is_primary_contact` (boolean)

## Relationships

- `clients (1) -> (N) invoices` via `invoices.client_id`
- `clients (1) -> (N) client_products` via `client_products.client_id`
- `clients (1) -> (N) client_employees` via `client_employees.client_id`

## Notes

- IDs are mock values for development/testing.
- Dates are UTC-compatible strings.
- These files are intended as seed-like fixtures, not production data.
