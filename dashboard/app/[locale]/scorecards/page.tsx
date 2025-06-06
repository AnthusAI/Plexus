"use client"

import { redirect } from 'next/navigation'

export default function Scorecards() {
  // Redirect to the lab version
  redirect('/lab/scorecards')
}
