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
        // Catch TypeScript errors in all environments to match production
        ignoreBuildErrors: false,
    },
    // Only include type checking on your own code files
    transpilePackages: []
}

module.exports = withHydrationOverlay()(nextConfig);