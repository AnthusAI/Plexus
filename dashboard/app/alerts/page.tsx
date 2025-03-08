"use client";

import { redirect } from 'next/navigation'

export default function Alerts() {
  // Redirect to the lab version
  redirect('/lab/alerts')
}
