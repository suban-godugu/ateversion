import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone is for Docker images; Vercel uses its own build output
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
