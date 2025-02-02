import { Section } from './StandardSection'
import type { SectionProps } from './StandardSection'

export const FrameSection = (props: Omit<SectionProps, 'variant'>) => (
  <Section {...props} variant="framed" />
)

export default FrameSection