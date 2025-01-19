const { withHydrationOverlay } = require("@builder.io/react-hydration-overlay/next");

/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverComponentsExternalPackages: ['@aws-crypto'],
    },
    eslint: {
        ignoreDuringBuilds: false,
        dirs: ['app', 'components', 'utils', 'stories']
    }
}

module.exports = nextConfig;