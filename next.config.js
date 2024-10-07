/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverComponentsExternalPackages: ['@aws-crypto'],
    }
}

module.exports = nextConfig