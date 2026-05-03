import packageJson from "../package.json";

/**
 * Version affichée (header, commande `version` du shell).
 * Surcharge build / Vercel : NEXT_PUBLIC_APP_VERSION (ex. alignée sur PyPI onchor-ai).
 */
export const APP_VERSION =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_APP_VERSION?.trim()) ||
  packageJson.version;
