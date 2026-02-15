# Adding a New District

Graider uses district-specific configs to automate Outlook email sending through each district's SSO portal. Each district is a single JSON file in `backend/districts/`.

## How It Works

1. Teacher saves their school email in Settings (e.g. `acrionas@volusia.k12.fl.us`)
2. Graider auto-detects the district from the email domain
3. The matching district config tells Playwright which portal to visit and which selectors to use for login

## Adding a New District

1. Create `backend/districts/<district_id>.json`:

```json
{
  "id": "my_district",
  "name": "My District Schools",
  "portal_url": "https://portal.mydistrict.k12.fl.us/",
  "sso_type": "classlink",
  "email_domain": "mydistrict.k12.fl.us",
  "selectors": {
    "username_field": "",
    "password_field": "",
    "login_button": "",
    "outlook_tile": ""
  },
  "notes": ""
}
```

2. Run Playwright codegen to capture the selectors:

```bash
source venv/bin/activate
python -m playwright codegen https://portal.mydistrict.k12.fl.us/
```

3. Walk through the login flow manually. Codegen will record the selectors for each field you interact with. Copy those into the JSON config.

4. Test with:

```bash
python backend/services/outlook_sender.py --login-only
```

## Supported SSO Types

- `classlink` — ClassLink LaunchPad (Volusia, many FL districts)
- `clever` — Clever SSO
- `google` — Google Workspace SSO
- `microsoft` — Direct Microsoft 365 login

## District Config Fields

| Field | Description |
|-------|-------------|
| `id` | Short identifier, matches filename |
| `name` | Human-readable district name |
| `portal_url` | URL of the district's SSO portal |
| `sso_type` | SSO provider type (classlink, clever, google, microsoft) |
| `email_domain` | Domain used for auto-detection from teacher email |
| `selectors` | CSS/aria selectors captured via playwright codegen |
| `notes` | Any special behavior (redirects, 2FA, etc.) |
