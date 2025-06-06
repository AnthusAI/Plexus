"use client";

import { redirect } from 'next/navigation'

export default function Batches() {
  // Redirect to the lab version
  redirect('/lab/batches')
}
