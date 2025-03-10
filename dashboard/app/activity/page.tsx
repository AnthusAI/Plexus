"use client";

import { redirect } from 'next/navigation'

export default function Activity() {
  // Redirect to the lab version
  redirect('/lab/activity')
}
