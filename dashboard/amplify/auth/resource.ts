import { defineAuth } from "@aws-amplify/backend";

/**
 * Define and configure your auth resource
 * @see https://docs.amplify.aws/gen2/build-a-backend/auth
 */
export const auth = defineAuth({
  loginWith: {
    email: true,
    externalProviders: {
      oauth: {
        // This fixed, loopback-only callback is the stable contract consumed by
        // the official `plexus login` authorization-code flow.
        callbackUrls: ['http://127.0.0.1:8765/callback'],
        logoutUrls: ['http://127.0.0.1:8765/logout'],
        scopes: ['OPENID', 'EMAIL', 'PROFILE'],
      },
    },
  },
});
