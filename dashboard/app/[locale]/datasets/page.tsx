"use client";

import { redirect } from 'next/navigation'

export default function Datasets() {
  // Redirect to the lab version
  redirect('/lab/datasets')
}
