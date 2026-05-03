import packageJson from "../package.json";

/**
 * Displayed version (header, shell `version` command).
 * Build/Vercel override: NEXT_PUBLIC_APP_VERSION (e.g. aligned with PyPI onchor-ai).
 */
export const APP_VERSION =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_APP_VERSION?.trim()) ||
  packageJson.version;
