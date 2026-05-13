/**
 * Jest stub: next-intl navigation is ESM-heavy; tests use Next.js primitives instead.
 */
export { default as Link } from "next/link";
export { usePathname, useRouter, redirect } from "next/navigation";

export function getPathname() {
  return "/";
}
