import React from 'react'

export interface StandardSectionProps {
  headline: string;
  headlinePosition: 'top' | 'inline';
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  // For full-width content:
  fullWidth?: boolean;
  children?: React.ReactNode;
  // Optional: additional container classes if needed
  containerClassName?: string;
}

export const StandardSection: React.FC<StandardSectionProps> = ({
  headline,
  headlinePosition,
  leftContent,
  rightContent,
  fullWidth,
  children,
  containerClassName
}) => {
  return (
    <section className={`py-12 ${containerClassName || 'bg-background'}`}>
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="bg-background rounded-xl py-16 md:py-20 px-4 md:px-8">
            {headlinePosition === 'top' && (
              <h2 className="text-4xl md:text-5xl font-bold mb-10 text-foreground text-center">
                {headline}
              </h2>
            )}
            {fullWidth ? (
              children
            ) : (
              <div className="flex flex-col md:flex-row justify-between">
                <div className="w-full md:w-[45%] relative">
                  <div className="relative z-10">
                    {leftContent}
                  </div>
                </div>
                <div className="w-full md:w-1/2 text-center md:text-left">
                  {headlinePosition === 'inline' && (
                    <h2 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
                      {headline}
                    </h2>
                  )}
                  {rightContent}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default StandardSection; 