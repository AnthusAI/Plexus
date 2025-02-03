import React from 'react'

export interface SectionProps {
  headline: string;
  headlinePosition: 'top' | 'inline';
  variant?: 'standard' | 'framed';
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
  
  return (
    <section className={`${isFramed ? 'bg-muted' : 'py-8'} ${!isFramed ? (containerClassName || 'bg-background') : ''}`}>
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className={isFramed ? 'py-4' : 'py-2'}>
          <div className={`bg-background rounded-xl ${isFramed ? 'py-12 md:py-16' : 'py-8 md:py-12'} px-4 md:px-8`}>
            {headlinePosition === 'top' && (
              <h2 className={`text-3xl md:text-4xl font-bold ${isFramed ? 'mb-12' : 'mb-8'} text-center ${isFramed ? 'text-foreground' : 'text-foreground'}`}>
                {headline}
              </h2>
            )}
            {fullWidth || layout === 'single' ? (
              <>
                {headlinePosition === 'inline' && (
                  <h2 className={`text-3xl md:text-4xl font-bold ${isFramed ? 'mb-10' : 'mb-8'} text-center ${isFramed ? 'text-foreground' : 'text-foreground'}`}>
                    {headline}
                  </h2>
                )}
                {children}
              </>
            ) : (
              <div className="flex flex-col xl:flex-row gap-12">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-3rem)]">
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      {headlinePosition === 'inline' && (
                        <h2 className={`text-3xl md:text-4xl font-bold ${isFramed ? 'mb-6' : 'mb-6'} w-full ${isFramed ? 'text-foreground' : 'text-foreground'}`}>
                          {headline}
                        </h2>
                      )}
                      {leftContent}
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center items-center">
                      {rightContent}
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 xl:w-[calc(50%-3rem)] justify-center items-center">
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

export const StandardSection = (props: Omit<SectionProps, 'variant'>) => (
  <Section {...props} variant="standard" />
)

export { Section }
export default Section 