/** @type {import('next').NextConfig} */
const path = require('path')
const webpack = require('webpack')

const isLocalBackend =
    process.env.NEXT_PUBLIC_PLEXUS_BACKEND === 'local' ||
    process.env.PLEXUS_BACKEND_MODE === 'local'

const nextConfig = {
    serverExternalPackages: ['@aws-crypto'],
    typedRoutes: false,
    experimental: {
        // Use faster transpilation with SWC
        swcTraceProfiling: false,
        forceSwcTransforms: true,
    },
    typescript: {
        // Catch TypeScript errors in all environments to match production, unless fast build
        ignoreBuildErrors: process.env.NEXT_TYPESCRIPT_CHECK === '0',
        // Use tsc for type checking but not transpilation
        tsconfigPath: './tsconfig.json',
    },
    // Only include type checking on your own code files
    transpilePackages: [],
    // Optimize for faster builds
    compiler: {
        // Remove console logs in production
        removeConsole: process.env.NODE_ENV === 'production' ? {
            exclude: ['error']
        } : false,
    },
    webpack: (config, { dev, isServer }) => {
        // Handle AWS Amplify bundling issues
        config.resolve.fallback = {
            ...config.resolve.fallback,
            fs: false,
            net: false,
            tls: false,
        };

        if (isLocalBackend) {
            config.resolve.alias = {
                ...config.resolve.alias,
                'aws-amplify/data': path.resolve(__dirname, 'lib/local-amplify/data.ts'),
                'aws-amplify/api': path.resolve(__dirname, 'lib/local-amplify/data.ts'),
                'aws-amplify/auth': path.resolve(__dirname, 'lib/local-amplify/auth.ts'),
                'aws-amplify/storage': path.resolve(__dirname, 'lib/local-amplify/storage.ts'),
                '@aws-amplify/ui-react': path.resolve(__dirname, 'lib/local-amplify/ui-react.tsx'),
                '@aws-amplify/ui-react/styles.css': path.resolve(__dirname, 'lib/local-amplify/ui-react-styles.css'),
                '@aws-amplify/ui-react/styles.css$': path.resolve(__dirname, 'lib/local-amplify/ui-react-styles.css'),
            };
            config.plugins.push(
                new webpack.NormalModuleReplacementPlugin(
                    /^@aws-amplify\/ui-react\/styles\.css$/,
                    path.resolve(__dirname, 'lib/local-amplify/ui-react-styles.css'),
                ),
            );
        }

        config.module.rules.forEach(rule => {
            if (rule.oneOf) {
                rule.oneOf.forEach(one => {
                    if (one.use && Array.isArray(one.use)) {
                        one.use.forEach(use => {
                            if (use.loader && use.loader.includes('postcss-loader')) {
                                use.options.postcssOptions = {
                                    plugins: [
                                        '@tailwindcss/postcss',
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
module.exports = nextConfig;
