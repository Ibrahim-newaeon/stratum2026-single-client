# External Integrations

## Supported Platforms
- Google Ads API
- Meta Marketing API
- TikTok Ads API
- Snapchat Marketing API

## Adding New Integrations
1. Create service in `services/{platform}/`
2. Implement signal collector
3. Add health calculation logic
4. Register in integration registry
5. Document API requirements

## Authentication
Platform credentials are managed on the Integrations page
(`/dashboard/integrations`) and stored encrypted in the database
(`platform_app_credential`, resolved DB-first with env-var fallback —
see `services/oauth/credentials.py`). Each platform's required and
optional fields come from the `PLATFORM_FIELD_SPECS` registry there;
`POST /platform-credentials/{platform}/test` live-validates Meta and
WhatsApp against the Graph API.
Never commit credentials to the repository.
