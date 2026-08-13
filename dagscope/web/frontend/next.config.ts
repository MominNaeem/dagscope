import type { NextConfig } from 'next';

const config: NextConfig = {
  // Proxy all /api/* requests to the FastAPI backend during dev
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

export default config;
