import {redirect} from 'next/navigation';

// This page only renders when a user visits the root.
// Since we're using a [locale] structure, users should always be redirected to a locale.
export default function RootPage() {
  redirect('/en');
}