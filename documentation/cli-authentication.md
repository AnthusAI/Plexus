# CLI application authentication

`plexus login` is the only interactive human authentication path. It uses Cognito's authorization-code flow with PKCE and the fixed registered loopback callback `http://127.0.0.1:8765/callback`.

The Amplify auth resource creates the hosted authorization configuration, including that exact callback URI and the `openid email profile` scopes. Deployment tooling must publish these values to the CLI runtime:

- `PLEXUS_COGNITO_DOMAIN`: the HTTPS Cognito hosted-authorization domain, including the scheme.
- `PLEXUS_COGNITO_CLIENT_ID`: the User Pool application client ID.
- `PLEXUS_COGNITO_REGION`: the User Pool region, retained as deployment identity metadata.

The first two variables are required for the CLI. The deployed Amplify output already supplies the client ID and region; the OAuth domain becomes available after the hosted authorization resource is deployed and is supplied as `PLEXUS_COGNITO_DOMAIN` by the runtime environment. The CLI does not derive credentials from AWS SSO, an API key, or an account membership claim.

The browser callback binds only to `127.0.0.1`; if port 8765 is occupied, login fails with a clear retry message. The refresh credential is held in the operating-system keychain. Access tokens are obtained when needed and sent only through the explicit `PLEXUS_GRAPHQL_AUTH_MODE=cognito` bearer mode. `plexus logout` revokes and removes the refresh credential.
