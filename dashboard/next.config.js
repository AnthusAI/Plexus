const { withHydrationOverlay } = require("@builder.io/react-hydration-overlay/next");

/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverComponentsExternalPackages: ['@aws-crypto'],
    },
    eslint: {
        ignoreDuringBuilds: false,
        dirs: ['app', 'components', 'utils', 'stories']
    },
    typescript: {
        // Speed up type checking in all environments
        ignoreBuildErrors: true,
    },
    // Only include type checking on your own code files
    transpilePackages: []
}

module.exports = withHydrationOverlay()(nextConfig);