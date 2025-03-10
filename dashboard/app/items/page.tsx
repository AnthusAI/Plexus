"use client";

import { redirect } from 'next/navigation'

export default function Items() {
  // Redirect to the lab version
  redirect('/lab/items')
}