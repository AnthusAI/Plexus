# CLI application authentication

`plexus login` is the only interactive human authentication path. It uses Cognito's authorization-code flow with PKCE and the fixed registered loopback callback `http://127.0.0.1:8765/callback`.

The Amplify auth resource creates the hosted authorization configuration, including that exact callback URI and the `openid email profile` scopes. Deployment tooling must publish these values to the CLI runtime:

- `PLEXUS_COGNITO_DOMAIN`: the HTTPS Cognito hosted-authorization domain, including the scheme.
- `PLEXUS_COGNITO_CLIENT_ID`: the User Pool application client ID.
- `PLEXUS_COGNITO_REGION`: the User Pool region, retained as deployment identity metadata.

The CLI first reads the repo-local `dashboard/amplify_outputs.json`, then `amplify_outputs.json`, for `auth.user_pool_client_id`, `auth.aws_region`, and `auth.oauth.domain`. Explicit environment values take precedence. If the hosted authorization domain is absent, the user must deploy the Amplify OAuth configuration or supply the two required values; the CLI does not derive credentials from AWS SSO, an API key, or an account membership claim.

The browser callback binds only to `127.0.0.1` before the browser is opened; if port 8765 is occupied, login fails with a clear retry message. The refresh credential is held in the operating-system keychain. Access tokens are cached only in memory and refreshed 60 seconds before expiry. They are sent only through explicit Cognito bearer mode, either `PLEXUS_GRAPHQL_AUTH_MODE=cognito` or `PlexusDashboardClient(auth_mode="cognito")`. `plexus logout` revokes and removes the refresh credential.
