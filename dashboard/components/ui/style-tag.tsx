import React from 'react'
const animations = `
@keyframes jiggle {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-10deg); }
  75% { transform: rotate(10deg); }
}

@keyframes wave {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-20deg); }
  75% { transform: rotate(20deg); }
}

.animate-jiggle {
  animation: jiggle 1s ease-in-out infinite;
}

.animate-wave {
  animation: wave 1s ease-in-out infinite;
}
`

export function StyleTag() {
  return <style>{animations}</style>
} 