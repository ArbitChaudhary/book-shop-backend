# Backend Development Plan: Book Selling Platform

**Tech Stack:** FastAPI + PostgreSQL (Supabase) + Python
**Target:** Production-ready book marketplace with secure authentication, role-based access control, merchant management, orders, payments, and administration.

The platform will have three primary roles:

1. **Admin** — Manages the entire platform, users, merchants, books, orders, and system settings.
2. **User (Customer)** — Browses books, manages a cart, places orders, and tracks purchases.
3. **Merchant (Book Seller)** — Adds and manages books, manages inventory, and processes customer orders.

The backend should be designed as a modular application rather than a collection of basic CRUD endpoints. Security, database integrity, authorization, and operational reliability should be considered from the beginning.

## 1. High-Level Architecture

```text
                    FRONTEND
               Web / Mobile App
                       │
                       ▼
                 HTTPS / TLS
                       │
                       ▼
                 FASTAPI API
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Auth & RBAC   Business Logic  Validation
          │            │            │
          └────────────┼────────────┘
                       │
              Data Access Layer
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   Supabase PostgreSQL       Supabase Storage
   Users, Books, Orders      Book covers, media
   Inventory, Payments
          │
          ▼
    External Services
    Payment Provider
    Email / Notifications
```

### Recommended approach

- **FastAPI:** API framework and request handling.
- **Supabase PostgreSQL:** Primary relational database.
- **Supabase Auth:** Identity management, email verification, password reset, and optional social login.
- **SQLAlchemy 2.x + Alembic:** Database models, queries, and migrations.
- **Pydantic v2:** Request and response validation.
- **Redis:** Rate limiting, caching, and background task support when needed.
- **Celery or a managed job system:** For reliable background processing at scale.
- **Docker:** Consistent development and production deployment.
- **Sentry or equivalent:** Error monitoring.
- **GitHub Actions:** Automated testing and deployment.

**Important:** Supabase Auth and PostgreSQL authorization are different concerns. FastAPI must validate authenticated users and enforce application permissions. PostgreSQL Row Level Security (RLS) should provide an additional database-level protection layer where appropriate.

---

# 2. Role-Based Access Control

## Role hierarchy

```text
Admin
 ├── Platform management
 ├── User management
 ├── Merchant management
 ├── Book management
 ├── Order management
 └── Reports and settings

Merchant
 ├── Merchant profile
 ├── Own books
 ├── Own inventory
 ├── Own orders
 └── Sales reports

User
 ├── Profile
 ├── Browse books
 ├── Cart and wishlist
 ├── Own orders
 └── Reviews
```

### Permission design

Do not rely solely on the role name. Use explicit permissions internally.

For example:

```text
books:create
books:read
books:update
books:delete

orders:create
orders:read_own
orders:read_all
orders:update_status

merchants:approve
merchants:suspend

users:manage
reports:read
```

This makes the system easier to extend if you later add roles such as support staff, warehouse staff, or moderators.

## Role permission matrix

| Feature                  |           Admin |        Merchant | User |
| ------------------------ | --------------: | --------------: | ---: |
| Browse books             |             Yes |             Yes |  Yes |
| Manage own profile       |             Yes |             Yes |  Yes |
| Create books             |             Yes |             Yes |   No |
| Edit own books           |             Yes |             Yes |   No |
| Edit any book            |             Yes |              No |   No |
| Delete own books         |             Yes |             Yes |   No |
| Manage own inventory     |             Yes |             Yes |   No |
| View own orders          |             Yes |           Yes\* |  Yes |
| View all orders          |             Yes |              No |   No |
| Place orders             | Yes, if enabled | Yes, if enabled |  Yes |
| Manage users             |             Yes |              No |   No |
| Approve merchants        |             Yes |              No |   No |
| Suspend merchants        |             Yes |              No |   No |
| View platform reports    |             Yes |  Own sales only |   No |
| Manage platform settings |             Yes |              No |   No |

\*A merchant should see only the order information required to fulfill orders involving that merchant's books.

**Security rule:** Never trust a `user_id`, `merchant_id`, or `role` sent by the frontend. Derive the authenticated user's identity from a verified token and enforce ownership or role permissions on the server.

# 3. Database Design

The database should be relational and normalized, with foreign keys, indexes, constraints, and transactions.

Use **UUIDs** as primary keys for users, books, merchants, and orders.

## 3.1 Users and Authentication

Supabase Auth manages authentication identities. Your application database stores additional user information.

### `profiles`

| Column     | Type      | Description                      |
| ---------- | --------- | -------------------------------- |
| id         | UUID, PK  | References Supabase Auth user ID |
| full_name  | VARCHAR   | User's name                      |
| phone      | VARCHAR   | Optional phone number            |
| avatar_url | TEXT      | Profile image                    |
| status     | ENUM      | active, suspended, deleted       |
| created_at | TIMESTAMP | Creation time                    |
| updated_at | TIMESTAMP | Last update                      |

### `user_roles`

| Column     | Type      | Description           |
| ---------- | --------- | --------------------- |
| id         | UUID, PK  | Role assignment ID    |
| user_id    | UUID, FK  | User                  |
| role       | ENUM      | admin, user, merchant |
| created_at | TIMESTAMP | Assignment time       |

**Recommendation:** Enforce one primary role per account initially. If you later support multiple roles, use a unique constraint on `(user_id, role)` and explicitly design how permissions are combined.

### Important security considerations

- Do not allow users to assign themselves the `admin` or `merchant` role.
- New accounts should default to `user`.
- Merchant access should require admin approval.
- Role changes must be logged.
- Never expose privileged Supabase service-role credentials to the frontend.

---

## 3.2 Merchant Management

### `merchants`

| Column               | Type      | Description                 |
| -------------------- | --------- | --------------------------- |
| id                   | UUID, PK  | Merchant ID                 |
| user_id              | UUID, FK  | Owner account               |
| business_name        | VARCHAR   | Store name                  |
| business_description | TEXT      | Description                 |
| contact_email        | VARCHAR   | Business email              |
| contact_phone        | VARCHAR   | Business phone              |
| address              | JSONB     | Business address            |
| verification_status  | ENUM      | pending, approved, rejected |
| status               | ENUM      | active, suspended, closed   |
| approved_by          | UUID, FK  | Admin who approved          |
| approved_at          | TIMESTAMP | Approval time               |
| created_at           | TIMESTAMP | Creation time               |

### Merchant workflow

```text
User registers
      │
      ▼
Requests merchant access
      │
      ▼
Merchant application = PENDING
      │
      ▼
Admin reviews application
      │
      ├── Reject
      │
      └── Approve
             │
             ▼
       Merchant activated
```

A merchant should not be able to publish books or receive seller privileges until the required approval process is complete.

---

# 4. Book Catalog Design

## 4.1 `books`

| Column           | Type            | Description                                   |
| ---------------- | --------------- | --------------------------------------------- |
| id               | UUID, PK        | Book ID                                       |
| merchant_id      | UUID, FK        | Seller                                        |
| title            | VARCHAR         | Book title                                    |
| slug             | VARCHAR, UNIQUE | SEO-friendly URL                              |
| description      | TEXT            | Book description                              |
| isbn_10          | VARCHAR         | Optional ISBN-10                              |
| isbn_13          | VARCHAR         | Optional ISBN-13                              |
| author_name      | VARCHAR         | Author                                        |
| publisher        | VARCHAR         | Publisher                                     |
| publication_date | DATE            | Publication date                              |
| language         | VARCHAR         | Book language                                 |
| page_count       | INTEGER         | Number of pages                               |
| category_id      | UUID, FK        | Category                                      |
| cover_image_url  | TEXT            | Cover image                                   |
| price            | NUMERIC(12,2)   | Selling price                                 |
| status           | ENUM            | draft, pending, published, rejected, archived |
| created_at       | TIMESTAMP       | Creation time                                 |
| updated_at       | TIMESTAMP       | Last update                                   |

### Additional tables

#### `categories`

- id
- name
- slug
- description
- parent_id
- status

#### `authors`

- id
- name
- biography
- photo_url

#### `book_authors`

- book_id
- author_id

#### `book_images`

- id
- book_id
- image_url
- image_type
- sort_order

#### `book_tags`

- book_id
- tag_id

#### `tags`

- id
- name
- slug

### Book publication workflow

```text
Merchant creates book
        │
        ▼
       DRAFT
        │
        ▼
Merchant submits book
        │
        ▼
      PENDING
        │
        ▼
Admin reviews
    ┌───┴────┐
    ▼        ▼
APPROVED  REJECTED
    │
    ▼
 PUBLISHED
```

You can allow trusted merchants to publish automatically later, but admin moderation is a safer initial production approach.

---

# 5. Inventory Management

Inventory must be designed carefully to avoid selling more books than are available.

## `inventory`

| Column              | Type      | Description     |
| ------------------- | --------- | --------------- |
| id                  | UUID, PK  | Inventory ID    |
| book_id             | UUID, FK  | Book            |
| quantity_available  | INTEGER   | Available stock |
| quantity_reserved   | INTEGER   | Reserved stock  |
| low_stock_threshold | INTEGER   | Alert threshold |
| updated_at          | TIMESTAMP | Last update     |

### Available stock formula

```text
Available to purchase =
quantity_available - quantity_reserved
```

Alternatively, define `quantity_available` as the remaining sellable stock and maintain reservations separately. Choose one interpretation and use it consistently.

### Inventory operations

- Add stock
- Reduce stock
- Reserve stock
- Release reservation
- Confirm sale
- Adjust stock
- Record inventory history

## `inventory_transactions`

Track every stock change:

| Column           | Description                            |
| ---------------- | -------------------------------------- |
| id               | Transaction ID                         |
| book_id          | Book                                   |
| merchant_id      | Merchant                               |
| quantity_change  | Positive or negative                   |
| transaction_type | sale, restock, adjustment, reservation |
| reference_id     | Related order or operation             |
| created_by       | User or system                         |
| created_at       | Timestamp                              |

### Critical concurrency rule

When placing an order, inventory reservation must occur inside a database transaction.

Use row-level locking or an atomic conditional update, for example:

```sql
UPDATE inventory
SET quantity_available = quantity_available - :quantity
WHERE book_id = :book_id
  AND quantity_available >= :quantity;
```

Then verify that exactly one row was updated.

Do not:

1. Read the stock.
2. Check it in Python.
3. Update it later without a transaction.

That approach can cause overselling when multiple customers purchase simultaneously.

---

# 6. Shopping Cart and Wishlist

## `carts`

| Column     | Description   |
| ---------- | ------------- |
| id         | Cart ID       |
| user_id    | Customer      |
| created_at | Creation time |
| updated_at | Last update   |

## `cart_items`

| Column     | Description        |
| ---------- | ------------------ |
| id         | Item ID            |
| cart_id    | Cart               |
| book_id    | Book               |
| quantity   | Requested quantity |
| created_at | Creation time      |

Add a unique constraint on:

```text
(cart_id, book_id)
```

A user should have one active cart.

### Cart features

- Add book
- Remove book
- Update quantity
- View cart
- Validate book availability
- Validate current price
- Calculate subtotal
- Check merchant and product status

**Important:** Cart prices should not be trusted during checkout. Recalculate prices from the database when creating the order.

## `wishlists`

| Column     | Description |
| ---------- | ----------- |
| id         | Wishlist ID |
| user_id    | Customer    |
| book_id    | Book        |
| created_at | Timestamp   |

Add a unique constraint on `(user_id, book_id)`.

---

# 7. Order Management

Orders are one of the most important backend modules.

## 7.1 `orders`

| Column           | Type            | Description                                                             |
| ---------------- | --------------- | ----------------------------------------------------------------------- |
| id               | UUID, PK        | Order ID                                                                |
| order_number     | VARCHAR, UNIQUE | Public order number                                                     |
| user_id          | UUID, FK        | Customer                                                                |
| status           | ENUM            | pending, confirmed, processing, shipped, delivered, cancelled, returned |
| payment_status   | ENUM            | pending, paid, failed, refunded, partially_refunded                     |
| subtotal         | NUMERIC(12,2)   | Item subtotal                                                           |
| shipping_fee     | NUMERIC(12,2)   | Shipping cost                                                           |
| discount_amount  | NUMERIC(12,2)   | Discount                                                                |
| total_amount     | NUMERIC(12,2)   | Final total                                                             |
| currency         | CHAR(3)         | Currency code                                                           |
| shipping_address | JSONB           | Snapshot of delivery address                                            |
| created_at       | TIMESTAMP       | Creation time                                                           |
| updated_at       | TIMESTAMP       | Last update                                                             |

## 7.2 `order_items`

| Column             | Description                                        |
| ------------------ | -------------------------------------------------- |
| id                 | Item ID                                            |
| order_id           | Order                                              |
| book_id            | Book                                               |
| merchant_id        | Merchant                                           |
| title_snapshot     | Book title at purchase                             |
| isbn_snapshot      | ISBN at purchase                                   |
| unit_price         | Price at purchase                                  |
| quantity           | Quantity purchased                                 |
| total_price        | Item total                                         |
| fulfillment_status | pending, processing, shipped, delivered, cancelled |

### Why snapshots matter

If a merchant changes a book's title or price later, the old order must still show the original information.

Do not depend exclusively on the current `books` table to display historical orders.

---

# 8. Multi-Merchant Order Architecture

Because your platform allows multiple merchants, one customer order may contain books from different sellers.

Example:

```text
Customer places order
        │
        ▼
Order #1001
        │
        ├── Merchant A
        │     ├── Book 1
        │     └── Book 2
        │
        └── Merchant B
              └── Book 3
```

For production, consider introducing merchant-specific fulfillment orders.

## `merchant_orders`

| Column       | Description           |
| ------------ | --------------------- |
| id           | Merchant order ID     |
| order_id     | Parent customer order |
| merchant_id  | Seller                |
| status       | Fulfillment status    |
| subtotal     | Merchant subtotal     |
| shipping_fee | Merchant shipping fee |
| total_amount | Merchant total        |
| created_at   | Timestamp             |

This allows:

- Each merchant to manage only their own fulfillment.
- Separate shipping statuses.
- Merchant-specific reporting.
- Commission calculation.
- Partial cancellations and returns.

### Recommended order structure

```text
orders
   │
   └── merchant_orders
          │
          └── order_items
```

---

# 9. Payment System

The payment provider should be selected based on the countries and payment methods you intend to support.

For a Nepal-focused platform, investigate locally supported payment providers and their current merchant/API capabilities before implementation.

## `payments`

| Column                  | Description                                     |
| ----------------------- | ----------------------------------------------- |
| id                      | Payment ID                                      |
| order_id                | Order                                           |
| provider                | Payment provider                                |
| provider_transaction_id | External transaction ID                         |
| amount                  | Amount                                          |
| currency                | Currency                                        |
| status                  | initiated, pending, succeeded, failed, refunded |
| payment_method          | Method                                          |
| provider_response       | Sanitized JSONB                                 |
| created_at              | Timestamp                                       |
| updated_at              | Timestamp                                       |

## Payment workflow

```text
Customer checkout
       │
       ▼
Create pending order
       │
       ▼
Reserve inventory
       │
       ▼
Create payment request
       │
       ▼
Customer completes payment
       │
       ▼
Payment provider callback/webhook
       │
       ▼
Verify payment independently
       │
       ├── Failed → Release inventory
       │
       └── Successful
              │
              ▼
       Mark order as paid
              │
              ▼
       Confirm fulfillment
```

### Payment security rules

- Never trust payment success information sent directly by the browser.
- Verify payment status with the provider.
- Validate amount, currency, order ID, and transaction ID.
- Verify webhook signatures.
- Make webhook processing idempotent.
- Never store raw card numbers or CVV.
- Use payment provider-hosted checkout or tokenized payment flows where possible.
- Never mark an order as paid solely because a frontend request says it succeeded.

---

# 10. Merchant Earnings and Commission

If your platform takes a commission, create a financial ledger rather than calculating earnings only from current order data.

## `merchant_transactions`

| Column            | Description                      |
| ----------------- | -------------------------------- |
| id                | Transaction ID                   |
| merchant_id       | Merchant                         |
| order_id          | Related order                    |
| transaction_type  | sale, commission, refund, payout |
| gross_amount      | Gross amount                     |
| commission_amount | Platform commission              |
| net_amount        | Merchant amount                  |
| status            | pending, completed, reversed     |
| created_at        | Timestamp                        |

## `merchant_payouts`

| Column             | Description                       |
| ------------------ | --------------------------------- |
| id                 | Payout ID                         |
| merchant_id        | Merchant                          |
| amount             | Payout amount                     |
| status             | pending, processing, paid, failed |
| provider_reference | External reference                |
| processed_by       | Admin/system                      |
| created_at         | Timestamp                         |

### Financial integrity

- Use `NUMERIC`, never floating-point values, for money.
- Keep immutable financial records.
- Record refunds and reversals explicitly.
- Use idempotency keys for payment and payout operations.
- Reconcile platform records against payment provider reports.
- Restrict financial actions to authorized roles.

---

# 11. Address and Delivery Management

## `addresses`

| Column       | Description     |
| ------------ | --------------- |
| id           | Address ID      |
| user_id      | Customer        |
| full_name    | Recipient       |
| phone        | Contact number  |
| address_line | Address         |
| city         | City            |
| district     | District        |
| province     | Province        |
| postal_code  | Postal code     |
| is_default   | Default address |

At checkout, copy the selected address into the order as a snapshot.

### Delivery features

- Add and edit addresses.
- Select delivery address.
- Shipping fee calculation.
- Delivery status.
- Tracking number.
- Merchant-specific shipment tracking.
- Delivery confirmation.
- Failed delivery handling.

---

# 12. Reviews and Ratings

## `reviews`

| Column        | Description                 |
| ------------- | --------------------------- |
| id            | Review ID                   |
| book_id       | Book                        |
| user_id       | Customer                    |
| order_item_id | Purchased item              |
| rating        | 1–5                         |
| title         | Review title                |
| content       | Review content              |
| status        | pending, approved, rejected |
| created_at    | Timestamp                   |

### Rules

- Only customers who purchased the book can review it.
- Enforce one review per eligible order item, or define your preferred review policy.
- Customers can edit or delete their own reviews within the allowed policy.
- Admins can moderate reviews.
- Prevent review manipulation through rate limits and validation.

---

# 13. API Structure

Organize the FastAPI application by business domain.

```text
book-platform-backend/
│
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── permissions.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── base.py
│   │   └── migrations/
│   │
│   ├── models/
│   │   ├── profile.py
│   │   ├── role.py
│   │   ├── merchant.py
│   │   ├── book.py
│   │   ├── category.py
│   │   ├── inventory.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   ├── payment.py
│   │   └── review.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── merchant.py
│   │   ├── book.py
│   │   ├── inventory.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   └── payment.py
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── merchants.py
│   │       ├── books.py
│   │       ├── categories.py
│   │       ├── inventory.py
│   │       ├── cart.py
│   │       ├── orders.py
│   │       ├── payments.py
│   │       ├── reviews.py
│   │       └── admin.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── merchant_service.py
│   │   ├── book_service.py
│   │   ├── inventory_service.py
│   │   ├── order_service.py
│   │   ├── payment_service.py
│   │   └── notification_service.py
│   │
│   ├── repositories/
│   │   ├── book_repository.py
│   │   ├── order_repository.py
│   │   └── merchant_repository.py
│   │
│   ├── tasks/
│   │   ├── emails.py
│   │   ├── cleanup.py
│   │   └── reconciliation.py
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── security/
│
├── alembic.ini
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## API versioning

Use:

```text
/api/v1/
```

This allows you to introduce `/api/v2/` later without breaking existing clients.

---

# 14. Core API Endpoints

## Authentication

If Supabase Auth handles authentication, FastAPI mainly validates Supabase access tokens and manages application-specific profile and role operations.

```http
GET    /api/v1/auth/me
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/request-merchant-access
```

Password signup, login, email verification, and password reset should use Supabase Auth's supported flows.

## Users

```http
GET    /api/v1/users/me
PATCH  /api/v1/users/me
GET    /api/v1/users/me/addresses
POST   /api/v1/users/me/addresses
PATCH  /api/v1/users/me/addresses/{id}
DELETE /api/v1/users/me/addresses/{id}
```

## Merchant

```http
POST   /api/v1/merchants/apply
GET    /api/v1/merchants/me
PATCH  /api/v1/merchants/me
GET    /api/v1/merchants/me/books
GET    /api/v1/merchants/me/orders
GET    /api/v1/merchants/me/reports
```

## Books

```http
GET    /api/v1/books
GET    /api/v1/books/{book_id}
POST   /api/v1/books
PATCH  /api/v1/books/{book_id}
DELETE /api/v1/books/{book_id}
POST   /api/v1/books/{book_id}/submit
```

The create, update, delete, and submit operations must enforce merchant ownership and approval status.

## Categories

```http
GET    /api/v1/categories
POST   /api/v1/categories
PATCH  /api/v1/categories/{category_id}
DELETE /api/v1/categories/{category_id}
```

Writing operations should be restricted to authorized administrators.

## Cart

```http
GET    /api/v1/cart
POST   /api/v1/cart/items
PATCH  /api/v1/cart/items/{item_id}
DELETE /api/v1/cart/items/{item_id}
DELETE /api/v1/cart
```

## Orders

```http
POST   /api/v1/orders
GET    /api/v1/orders
GET    /api/v1/orders/{order_id}
POST   /api/v1/orders/{order_id}/cancel
```

## Payments

```http
POST   /api/v1/payments/create
GET    /api/v1/payments/{payment_id}
POST   /api/v1/payments/webhook
```

## Reviews

```http
GET    /api/v1/books/{book_id}/reviews
POST   /api/v1/books/{book_id}/reviews
PATCH  /api/v1/reviews/{review_id}
DELETE /api/v1/reviews/{review_id}
```

## Admin

```http
GET    /api/v1/admin/dashboard
GET    /api/v1/admin/users
PATCH  /api/v1/admin/users/{user_id}/status

GET    /api/v1/admin/merchants
POST   /api/v1/admin/merchants/{merchant_id}/approve
POST   /api/v1/admin/merchants/{merchant_id}/reject
POST   /api/v1/admin/merchants/{merchant_id}/suspend

GET    /api/v1/admin/books
POST   /api/v1/admin/books/{book_id}/approve
POST   /api/v1/admin/books/{book_id}/reject

GET    /api/v1/admin/orders
GET    /api/v1/admin/payments
GET    /api/v1/admin/reports
```

---

# 15. Authentication and Authorization Implementation

## Recommended authentication flow

```text
User logs in through Supabase Auth
              │
              ▼
Supabase returns access token
              │
              ▼
Frontend sends token to FastAPI
              │
              ▼
FastAPI validates token
              │
              ▼
FastAPI identifies user
              │
              ▼
FastAPI loads roles and permissions
              │
              ▼
Endpoint checks authorization
              │
              ▼
Business logic executes
```

### FastAPI dependencies

Create reusable dependencies such as:

```python
get_current_user()
require_authenticated_user()
require_role("admin")
require_role("merchant")
require_permission("books:create")
require_merchant_owner()
```

### Ownership validation

For a merchant editing a book:

```text
1. Validate access token.
2. Retrieve authenticated user.
3. Verify user has merchant privileges.
4. Retrieve merchant profile.
5. Verify merchant owns the book.
6. Verify merchant is active.
7. Apply the update.
```

Never accept a merchant ID from the client as proof of ownership.

### JWT security

- Validate the token signature.
- Validate issuer and audience as appropriate for your Supabase project.
- Validate expiration.
- Reject malformed or expired tokens.
- Use a well-maintained JWT library.
- Handle key rotation according to Supabase's authentication configuration.
- Do not blindly trust decoded JWT payloads without verification.

---

# 16. Supabase PostgreSQL Security

## Database roles

Use separate database access patterns for:

### Application runtime

The FastAPI application should use a restricted database role with only the permissions it needs.

### Migrations

Database migrations should use a separate privileged connection, never exposed to the public application.

### Supabase administrative access

Supabase service-role credentials must remain server-side and should be used only when necessary.

## Row Level Security

Supabase PostgreSQL supports RLS. Use it as a defense-in-depth mechanism.

Example policies conceptually:

```text
Users:
  Can read and update their own profile.

Merchants:
  Can read and update their own merchant profile.

Books:
  Public users can read published books.
  Merchants can manage their own books.
  Admins can manage all books.

Orders:
  Customers can read their own orders.
  Merchants can read relevant fulfillment orders.
  Admins can read all orders.
```

**Important:** If FastAPI connects using a privileged database role that bypasses RLS, the API's authorization checks become critical. RLS does not replace server-side authorization.

### Database hardening

- Enable RLS on exposed tables where appropriate.
- Revoke unnecessary database privileges.
- Use foreign keys.
- Use `CHECK` constraints.
- Use unique constraints.
- Use non-negative quantity constraints.
- Use database transactions.
- Avoid exposing internal database errors to clients.
- Keep database credentials in environment variables or a secrets manager.

---

# 17. Production Security Checklist

Security should be implemented before launch, not added afterward.

## Authentication

- [ ] Supabase Auth configured correctly.
- [ ] Email verification enabled if required.
- [ ] Secure password reset flow.
- [ ] Short-lived access tokens where appropriate.
- [ ] Secure refresh-token handling.
- [ ] Session revocation strategy.
- [ ] Protection against account enumeration where applicable.
- [ ] Optional MFA for administrators.
- [ ] Admin accounts protected with stronger authentication.

## Authorization

- [ ] Server-side role checks.
- [ ] Server-side ownership checks.
- [ ] Merchant approval enforcement.
- [ ] Admin-only endpoints protected.
- [ ] Suspended accounts blocked from restricted operations.
- [ ] No client-controlled role assignment.
- [ ] No client-controlled order ownership.
- [ ] No IDOR vulnerabilities.

**IDOR example to prevent:**

```http
GET /api/v1/orders/some-other-users-order-id
```

The backend must verify that the authenticated user has permission to access that order.

## API security

- [ ] HTTPS in production.
- [ ] CORS restricted to trusted frontend origins.
- [ ] Request validation with Pydantic.
- [ ] Rate limiting.
- [ ] Request body size limits.
- [ ] Pagination limits.
- [ ] Query parameter validation.
- [ ] Protection against mass assignment.
- [ ] Secure error responses.
- [ ] No debug mode in production.
- [ ] No sensitive data in logs.
- [ ] Request correlation IDs.

## Database security

- [ ] Strong database credentials.
- [ ] TLS database connections.
- [ ] Restricted database users.
- [ ] RLS policies reviewed.
- [ ] Automated backups enabled.
- [ ] Restore procedure tested.
- [ ] Migration process documented.
- [ ] Database indexes reviewed.
- [ ] No arbitrary SQL from user input.

## File uploads

For book covers and merchant documents:

- [ ] Validate file type.
- [ ] Validate file size.
- [ ] Validate actual file content, not only its extension.
- [ ] Generate safe object names.
- [ ] Store files in controlled Supabase Storage buckets.
- [ ] Restrict upload permissions.
- [ ] Use signed URLs for private files.
- [ ] Prevent executable file uploads.
- [ ] Consider malware scanning for sensitive document uploads.

## Payment security

- [ ] Verify payment provider webhooks.
- [ ] Use idempotency.
- [ ] Verify amounts and currencies.
- [ ] Avoid storing card information.
- [ ] Keep financial audit logs.
- [ ] Reconcile payments.
- [ ] Secure refund operations.

---

# 18. Validation and Error Handling

Use consistent API responses.

### Success response

```json
{
  "success": true,
  "data": {
    "id": "book-id",
    "title": "Python Fundamentals"
  }
}
```

### Error response

```json
{
  "success": false,
  "error": {
    "code": "BOOK_NOT_FOUND",
    "message": "The requested book could not be found."
  }
}
```

Avoid returning:

- SQL queries.
- Stack traces.
- Database credentials.
- Internal file paths.
- Sensitive user information.
- Raw payment provider responses.

### HTTP status codes

| Status | Use                                       |
| ------ | ----------------------------------------- |
| 200    | Successful request                        |
| 201    | Resource created                          |
| 204    | Successful deletion with no response body |
| 400    | Invalid request                           |
| 401    | Missing or invalid authentication         |
| 403    | Insufficient permissions                  |
| 404    | Resource not found                        |
| 409    | Conflict                                  |
| 422    | Validation failure                        |
| 429    | Rate limit exceeded                       |
| 500    | Unexpected server error                   |

---

# 19. Testing Strategy

A production backend should not rely only on manual testing.

## Unit tests

Test individual functions:

- Price calculations.
- Commission calculations.
- Permission checks.
- Inventory calculations.
- Order status transitions.
- Validation rules.

## Integration tests

Test actual interactions between:

- FastAPI and PostgreSQL.
- FastAPI and Supabase Auth.
- FastAPI and Supabase Storage.
- Order creation and inventory reservation.
- Payment processing.
- Merchant approval workflow.

## Security tests

Test that:

- A user cannot access another user's order.
- A merchant cannot edit another merchant's book.
- A merchant cannot approve itself.
- A suspended merchant cannot publish books.
- A regular user cannot access admin endpoints.
- Invalid tokens are rejected.
- Expired tokens are rejected.
- Unauthorized role changes fail.
- Payment webhooks cannot be replayed.
- Inventory cannot become negative.
- SQL injection attempts are safely handled.

## Load tests

Test:

- Book listing.
- Search.
- Concurrent checkout.
- Inventory reservation.
- Login-related API traffic.
- Database connection pool behavior.

Recommended tools:

- `pytest`
- `pytest-asyncio`
- `httpx`
- `testcontainers`
- `Locust` or `k6`

---

# 20. Deployment Architecture

A practical production deployment could look like this:

```text
                    Users
                      │
                      ▼
               Frontend Hosting
                      │
                      ▼
                HTTPS / Domain
                      │
                      ▼
              FastAPI Application
                Docker Container
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      Supabase     Redis       Email Service
      PostgreSQL
          │
          ▼
   Supabase Storage
```

## Deployment options

You can deploy FastAPI on:

- Render
- Railway
- Fly.io
- AWS ECS/Fargate
- AWS App Runner
- Another managed container platform

Since you have worked with Render and FastAPI deployment before, Render can be a practical starting point. For a larger production workload, evaluate AWS or another platform based on scaling, operational requirements, and budget.

## Production environment variables

Example:

```env
APP_ENV=production
DEBUG=false

DATABASE_URL=your_private_database_connection
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_server_configured_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_private_server_only_key

JWT_AUDIENCE=your_configured_audience
JWT_ISSUER=your_configured_issuer

REDIS_URL=your_redis_url

PAYMENT_PROVIDER_KEY=your_private_key
PAYMENT_WEBHOOK_SECRET=your_webhook_secret

CORS_ORIGINS=https://your-frontend-domain.com
```

Do not commit `.env` files containing real secrets.

---

# 21. CI/CD Pipeline

Every pull request should run automated checks.

```text
Developer pushes code
         │
         ▼
      GitHub
         │
         ▼
   Pull Request
         │
         ▼
   CI Pipeline
         │
    ┌────┴─────────┐
    ▼              ▼
Linting         Automated Tests
    │              │
    └──────┬───────┘
           ▼
      Security Checks
           │
           ▼
      Build Docker Image
           │
           ▼
      Deploy to Staging
           │
           ▼
   Run Integration Tests
           │
           ▼
    Production Approval
           │
           ▼
    Deploy Production
```

### Recommended checks

- Ruff
- Pytest
- Mypy, if using type checking
- Dependency vulnerability scanning
- Secret scanning
- Docker image scanning
- Database migration validation
- API contract tests

---

# 22. Observability and Operations

You need to know when the system fails and why.

## Logging

Record:

- Request ID.
- Endpoint.
- HTTP method.
- Response status.
- Duration.
- Authenticated user ID where appropriate.
- Error category.
- Background task status.

Never log:

- Passwords.
- Access tokens.
- Refresh tokens.
- Payment secrets.
- Full sensitive addresses.
- Private personal documents.

## Monitoring

Monitor:

- API error rate.
- API latency.
- Database CPU and connections.
- Slow queries.
- Failed payments.
- Inventory reservation failures.
- Background task failures.
- Authentication failures.
- Storage usage.
- Database backup status.

## Audit logs

Create an `audit_logs` table.

| Column               | Description                         |
| -------------------- | ----------------------------------- |
| id                   | Log ID                              |
| actor_user_id        | Person or system                    |
| action               | Action performed                    |
| resource_type        | book, order, merchant, user         |
| resource_id          | Resource ID                         |
| metadata             | Sanitized JSONB                     |
| ip_hash_or_reference | Carefully handled security metadata |
| created_at           | Timestamp                           |

Record important actions such as:

- Admin role changes.
- Merchant approval.
- Merchant suspension.
- Book moderation.
- Refunds.
- Payouts.
- Inventory adjustments.
- Sensitive account changes.

---

# 23. Development Roadmap

Build the backend in phases instead of implementing everything simultaneously.

## Phase 1 — Project Foundation

**Goal:** Establish a clean, maintainable backend.

Tasks:

- [ ] Create FastAPI project.
- [ ] Configure Python environment.
- [ ] Configure PostgreSQL/Supabase.
- [ ] Configure SQLAlchemy.
- [ ] Configure Alembic.
- [ ] Create settings management.
- [ ] Configure logging.
- [ ] Configure Docker.
- [ ] Add health-check endpoint.
- [ ] Configure CI.
- [ ] Create initial database migration.

Deliverable:

> FastAPI application connected to Supabase PostgreSQL with a clean architecture.

---

## Phase 2 — Authentication and RBAC

**Goal:** Secure user access.

Tasks:

- [ ] Integrate Supabase Auth.
- [ ] Implement token verification.
- [ ] Create profiles.
- [ ] Create roles.
- [ ] Create permission dependencies.
- [ ] Implement admin authorization.
- [ ] Implement merchant application workflow.
- [ ] Add role-change audit logs.
- [ ] Add security tests.

Deliverable:

> Secure authentication and working admin, user, and merchant permissions.

---

## Phase 3 — Merchant and Catalog

**Goal:** Allow merchants to manage books.

Tasks:

- [ ] Create merchant schema.
- [ ] Implement merchant approval.
- [ ] Create categories.
- [ ] Create authors.
- [ ] Create books.
- [ ] Implement book CRUD.
- [ ] Implement ownership checks.
- [ ] Implement book moderation.
- [ ] Add cover image uploads.
- [ ] Add pagination and filtering.
- [ ] Add search indexes.

Deliverable:

> Approved merchants can submit books, and customers can browse published books.

---

## Phase 4 — Inventory

**Goal:** Build reliable stock management.

Tasks:

- [ ] Create inventory tables.
- [ ] Add inventory transaction history.
- [ ] Implement restocking.
- [ ] Implement stock adjustments.
- [ ] Implement reservations.
- [ ] Add database transactions.
- [ ] Test concurrent inventory updates.
- [ ] Add low-stock alerts.

Deliverable:

> Inventory is accurate and protected against overselling.

---

## Phase 5 — Cart and Checkout

**Goal:** Allow customers to prepare and place orders.

Tasks:

- [ ] Implement carts.
- [ ] Implement cart items.
- [ ] Implement wishlist.
- [ ] Validate prices at checkout.
- [ ] Validate stock.
- [ ] Create order snapshots.
- [ ] Implement merchant order splitting.
- [ ] Implement order state transitions.
- [ ] Add idempotency for order creation.

Deliverable:

> Customers can create reliable orders containing books from one or multiple merchants.

---

## Phase 6 — Payments and Fulfillment

**Goal:** Support real purchases.

Tasks:

- [ ] Select payment provider.
- [ ] Implement payment creation.
- [ ] Implement payment verification.
- [ ] Implement secure webhooks.
- [ ] Implement payment idempotency.
- [ ] Add payment status tracking.
- [ ] Implement merchant fulfillment.
- [ ] Implement delivery tracking.
- [ ] Implement cancellations and refunds.
- [ ] Implement merchant commission ledger.

Deliverable:

> The platform can process and track real orders and payments safely.

---

## Phase 7 — Admin Dashboard APIs

**Goal:** Provide complete platform administration.

Tasks:

- [ ] Admin dashboard metrics.
- [ ] User management.
- [ ] Merchant management.
- [ ] Book moderation.
- [ ] Order management.
- [ ] Payment monitoring.
- [ ] Refund management.
- [ ] Inventory monitoring.
- [ ] Audit log viewer.
- [ ] Reports and exports.

Deliverable:

> Admin can manage and monitor the platform through secure APIs.

---

## Phase 8 — Production Hardening

**Goal:** Prepare for real users.

Tasks:

- [ ] Complete security audit.
- [ ] Test authorization boundaries.
- [ ] Run load tests.
- [ ] Configure rate limiting.
- [ ] Configure backups.
- [ ] Test database restoration.
- [ ] Configure monitoring.
- [ ] Configure alerts.
- [ ] Test payment failure scenarios.
- [ ] Review database indexes.
- [ ] Review API documentation.
- [ ] Perform deployment rehearsal.
- [ ] Conduct final production readiness review.

Deliverable:

> A tested, monitored, deployable production backend.

---

# 24. Recommended MVP Scope

To launch sooner, you do not need every feature immediately.

## Must-have for first launch

- Authentication.
- User, admin, and merchant roles.
- Merchant approval.
- Book catalog.
- Categories.
- Book cover uploads.
- Inventory.
- Cart.
- Checkout.
- Orders.
- Payment integration.
- Merchant order management.
- Admin dashboard APIs.
- Secure authorization.
- Error handling.
- Logging.
- Automated tests.
- Backups and monitoring.

## Can be added after launch

- Wishlist.
- Reviews.
- Coupons.
- Advanced search.
- Recommendations.
- Multiple shipping providers.
- Merchant payouts.
- Loyalty points.
- Notifications.
- Analytics.
- Multi-language support.
- Advanced reporting.

---

# 25. Important Architectural Decisions

Before writing the first production endpoint, decide the following:

| Decision              | Recommendation                              |
| --------------------- | ------------------------------------------- |
| Authentication        | Supabase Auth                               |
| Database              | Supabase PostgreSQL                         |
| ORM                   | SQLAlchemy 2.x                              |
| Migrations            | Alembic                                     |
| API framework         | FastAPI                                     |
| Validation            | Pydantic v2                                 |
| Primary keys          | UUID                                        |
| Money                 | `NUMERIC(12,2)`                             |
| Database transactions | Required for checkout and inventory         |
| Role system           | RBAC with explicit permissions              |
| Merchant approval     | Admin-controlled                            |
| Book moderation       | Admin-controlled initially                  |
| Order structure       | Parent order + merchant orders              |
| Payment confirmation  | Verified provider webhook                   |
| File storage          | Supabase Storage                            |
| Deployment            | Docker + managed hosting                    |
| Testing               | Unit, integration, security, and load tests |
| API versioning        | `/api/v1`                                   |

---

# 26. Final Production Readiness Checklist

Before launch, confirm:

### Backend

- [ ] Clean modular architecture.
- [ ] Database migrations are reproducible.
- [ ] All endpoints have validation.
- [ ] All protected endpoints enforce authorization.
- [ ] All ownership checks are server-side.
- [ ] All critical operations use transactions.

### Security

- [ ] No secrets in Git.
- [ ] No exposed service-role credentials.
- [ ] HTTPS enabled.
- [ ] CORS restricted.
- [ ] Rate limiting enabled.
- [ ] Admin MFA considered or enabled.
- [ ] RLS policies reviewed.
- [ ] Security tests passed.
- [ ] Dependency vulnerabilities reviewed.

### Business logic

- [ ] Merchant approval works.
- [ ] Books cannot be published by unauthorized merchants.
- [ ] Inventory cannot become negative.
- [ ] Checkout cannot oversell stock.
- [ ] Prices are recalculated during checkout.
- [ ] Payment status is independently verified.
- [ ] Duplicate webhooks do not duplicate orders.
- [ ] Merchant order isolation works.
- [ ] Refunds are tracked correctly.

### Operations

- [ ] Backups enabled.
- [ ] Restoration tested.
- [ ] Monitoring enabled.
- [ ] Alerts configured.
- [ ] Logs are safe.
- [ ] CI/CD configured.
- [ ] Production deployment tested.
- [ ] Rollback procedure documented.

---

## My Recommended Starting Point

For your project, I would build the backend in this order:

**FastAPI foundation → Supabase Auth → RBAC → Merchant approval → Book catalog → Inventory → Cart → Orders → Payments → Admin APIs → Production hardening.**

The most important design decision is to build **authorization, inventory transactions, and order management correctly from the start**. These are much harder to repair after the platform has real users and transactions.

The next practical step is to turn this plan into a **complete backend technical specification**, including the PostgreSQL schema, SQLAlchemy models, API contracts, RBAC dependencies, and an implementation task list for FastAPI.
