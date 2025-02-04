import React from 'react'

export interface SectionProps {
  headline: React.ReactNode;
  headlinePosition: 'top' | 'inline';
  variant?: 'standard' | 'hero' | 'framed';
  layout?: 'twoColumn' | 'single';
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  rightColumnAlign?: 'top' | 'middle';
  fullWidth?: boolean;
  children?: React.ReactNode;
  containerClassName?: string;
}

const Section: React.FC<SectionProps> = ({
  headline,
  headlinePosition,
  variant = 'standard',
  layout = 'twoColumn',
  leftContent,
  rightContent,
  rightColumnAlign = 'top',
  fullWidth,
  children,
  containerClassName
}) => {
  const isFramed = variant === 'framed';
  const isHero = variant === 'hero';
  
  // Headline classes: hero uses a larger size
  const headlineClasses = isHero
    ? 'text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-8'
    : 'text-3xl md:text-4xl font-bold mb-6';

  return (
    <section 
      className={`${isFramed || isHero ? '' : 'py-8'} ${!isFramed && !isHero ? (containerClassName || 'bg-background') : ''}`}
      style={isFramed || isHero ? { background: 'var(--frame-bg)' } : undefined}
    >
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className={`py-4`}>
          <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
            {headlinePosition === 'top' && (
              <h2 className={`${headlineClasses} text-center`}>
                {headline}
              </h2>
            )}
            {fullWidth || layout === 'single' ? (
              <>
                {headlinePosition === 'inline' && (
                  <h2 className={`${headlineClasses} text-center`}>
                    {headline}
                  </h2>
                )}
                {children}
              </>
            ) : (
              <div className="flex flex-col xl:flex-row gap-12 min-h-[400px]">
                <div className={`flex-1 min-w-0 xl:w-[calc(50%-3rem)] flex ${rightColumnAlign === 'middle' ? 'items-center' : 'items-start'}`}>
                  <div className="w-full">
                    {headlinePosition === 'inline' && (
                      <h2 className={`${headlineClasses} w-full`}>
                        {headline}
                      </h2>
                    )}
                    <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                      <div className="w-full md:w-1/2 xl:w-full">
                        {leftContent}
                      </div>
                      <div className="w-full md:w-1/2 xl:hidden flex justify-center items-center">
                        {rightContent}
                      </div>
                    </div>
                  </div>
                </div>
                <div className={`hidden xl:flex flex-1 min-w-0 xl:w-[calc(50%-3rem)] justify-center ${rightColumnAlign === 'middle' ? 'items-center' : 'items-start'}`}>
                  {rightContent}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export const StandardSection = Section;

export { Section }
export default Section 