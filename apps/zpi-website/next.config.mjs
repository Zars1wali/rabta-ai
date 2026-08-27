/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@salesops/core', '@salesops/types', '@salesops/web'],
  webpack: (config) => {
    config.resolve.extensionAlias = {
      '.js': ['.ts', '.tsx', '.js', '.jsx']
    };
    return config;
  },
  reactStrictMode: true
};

export default nextConfig;
