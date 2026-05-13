import { routing } from "@/i18n/routing";

/** Strip `/{locale}` prefix from a pathname for route matching. */
export function pathWithoutLocale(pathname: string): string {
  for (const locale of routing.locales) {
    const prefix = `/${locale}`;
    if (pathname === prefix || pathname === `${prefix}/`) {
      return "/";
    }
    if (pathname.startsWith(`${prefix}/`)) {
      return pathname.slice(prefix.length);
    }
  }
  return pathname;
}
