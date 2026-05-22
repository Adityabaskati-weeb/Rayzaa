const watchIgnoreGlobs = [
  "**/.runtime/**",
  "**/.runtime_logs/**",
  "**/.artifacts/**",
  "**/.bench_artifacts/**",
  "**/.bench_artifacts2/**",
  "**/rayzaa.db*",
  "**/data/raw/**"
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.RAYZAA_NEXT_DIST_DIR || ".next",
  eslint: {
    ignoreDuringBuilds: true
  },
  typescript: {
    ignoreBuildErrors: true
  },
  experimental: {
    webpackBuildWorker: false
  },
  webpack(config, { dev }) {
    if (dev) {
      const existingIgnored = config.watchOptions?.ignored;
      const ignored = Array.isArray(existingIgnored)
        ? existingIgnored.filter((item) => typeof item === "string" && item.trim().length > 0)
        : typeof existingIgnored === "string" && existingIgnored.trim().length > 0
          ? [existingIgnored]
          : [];
      config.watchOptions = {
        ...(config.watchOptions || {}),
        ignored: [...ignored, ...watchIgnoreGlobs]
      };
    }
    return config;
  }
};

export default nextConfig;
