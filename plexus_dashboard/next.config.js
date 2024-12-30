const { withHydrationOverlay } = require("@builder.io/react-hydration-overlay/next");

/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverComponentsExternalPackages: ['@aws-crypto'],
    }
}

module.exports = withHydrationOverlay({
    appRootSelector: "body", // Adjust this if necessary
})(nextConfig);