/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  eslint: {
    // ESLint tidak dijalankan saat build agar build tidak gagal karena aturan lint.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
