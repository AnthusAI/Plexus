const { withHydrationOverlay } = require("@builder.io/react-hydration-overlay/next");

/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverComponentsExternalPackages: ['@aws-crypto'],
        // Use faster transpilation with SWC
        swcTraceProfiling: false,
        // Optimize for faster builds
        typedRoutes: false,
        forceSwcTransforms: true,
    },
    eslint: {
        ignoreDuringBuilds: process.env.NEXT_TYPESCRIPT_CHECK === '0',
        dirs: ['app', 'components', 'utils'],
        // Exclude stories from ESLint during builds
    },
    typescript: {
        // Catch TypeScript errors in all environments to match production, unless fast build
        ignoreBuildErrors: process.env.NEXT_TYPESCRIPT_CHECK === '0',
        // Use tsc for type checking but not transpilation
        tsconfigPath: './tsconfig.json',
    },
    // Only include type checking on your own code files
    transpilePackages: [],
    // Use SWC minifier for faster builds
    swcMinify: true,
    // Optimize for faster builds
    compiler: {
        // Remove console logs in production
        removeConsole: process.env.NODE_ENV === 'production' ? {
            exclude: ['error']
        } : false,
    },
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