import { redirect } from 'next/navigation'

export default function Evaluations() {
  // Add a permanent redirect to /lab/evaluations
  // This is a server-side redirect that will be cached by browsers
  redirect('/lab/evaluations')
}
