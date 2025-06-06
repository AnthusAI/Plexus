"use client";

import { redirect } from 'next/navigation'

export default function Settings() {
  // Redirect to the lab version
  redirect('/lab/settings')
}