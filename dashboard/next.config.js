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
    transpilePackages: [],
    webpack: (config, { dev, isServer }) => {
        config.module.rules.forEach(rule => {
            if (rule.oneOf) {
                rule.oneOf.forEach(one => {
                    if (one.use && Array.isArray(one.use)) {
                        one.use.forEach(use => {
                            if (use.loader && use.loader.includes('postcss-loader')) {
                                use.options.postcssOptions = {
                                    plugins: [
                                        'tailwindcss',
                                        'autoprefixer',
                                    ],
                                };
                            }
                        });
                    }
                });
            }
        });
        return config;
    },
}

module.exports = withHydrationOverlay()(nextConfig);