import createMiddleware from 'next-intl/middleware';
import {locales} from './i18n';

export default createMiddleware({
  // A list of all locales that are supported
  locales,
  
  // Used when no locale matches
  defaultLocale: process.env.DEFAULT_LOCALE || 'en',
  
  // The locale detection strategy
  localeDetection: true,
  
  // Prefix the default locale in the URL
  localePrefix: 'as-needed'
});

export const config = {
  // Match only internationalized pathnames
  matcher: [
    // Enable a redirect to a matching locale at the root
    '/',

    // Set a cookie to remember the locale for pages that don't have
    // internationalized pathnames
    '/((?!api|_next|_vercel|.*\\..*).*)'
  ]
};