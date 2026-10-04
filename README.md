# Jai Hanuman Sweets

A single-file Flask storefront with separate static CSS and JavaScript assets. The app creates its SQLite tables automatically on startup.

## Run locally

From PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The local database is `instance/single_sweet_shop.db`.

## Features

- Searchable product catalog with category, price, availability, sorting, pagination, and grid/list controls
- Product details with image lightbox, stock-aware quantities, reviews, related sweets, and wishlist
- Signed-in basket with quantity management, `SWEET10`/`MITHAI10`, delivery choices, and order confirmation
- Customer dashboard, order history, editable profile, settings, and resumable onboarding
- Admin operations dashboard, customer management, audit log, analytics, CSV exports, and internal order tools
- About, gifting/pricing, FAQ, maintenance, and branded error pages

## Admin access

Set `SWEET_SHOP_ADMIN_EMAILS` to a comma-separated list of administrator email addresses before starting the app. The addresses must belong to registered accounts.

```powershell
$env:SWEET_SHOP_ADMIN_EMAILS = "owner@example.com,manager@example.com"
python app.py
```

Sign in with an allowlisted account and open `/admin`. Admins can create customer or staff accounts at `/admin/users`. New accounts require a temporary password of at least 12 characters; share it securely.

## Checkout and integrations

Checkout supports cash on delivery only. No card numbers are collected and no online payment gateway is connected. Automated password-reset emails, social sign-in, and newsletter email delivery are not configured; newsletter signups are stored in SQLite.

For production, replace the demo `SECRET_KEY`, disable Flask debug mode, and run behind a production WSGI server.
Username: shopadmin
Password: jaez00AtUR9FWjApVeH6LKSC
Email: shopadmin@localhost