/** @type {import('next').NextConfig} */
const backend = process.env.CONVEAZY_API_URL || "http://127.0.0.1:8000";
const nextConfig = {
  poweredByHeader: false,
  async rewrites() {
    // Same-origin API: the session cookie never leaves the app's own domain.
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};
export default nextConfig;
