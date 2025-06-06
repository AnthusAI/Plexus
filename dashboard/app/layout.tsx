// Since we don't have a page directly under `/` that doesn't belong to a route group
// this layout will be used. However, we do want to redirect to the default locale, so we use a redirect.

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // This page only renders when a user visits the root.
  // Since we're using a [locale] structure, users should always be redirected to a locale.
  // The middleware handles this redirect.
  return (
    <html>
      <body>
        {children}
      </body>
    </html>
  );
}
