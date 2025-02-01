import React from 'react';

export interface FrameSectionProps {
  headline: string;
  layout?: 'twoColumn' | 'single';
  headlinePosition?: 'top' | 'inline';
  // For the two-column layout:
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  // For full-width content:
  fullWidth?: boolean;
  // For the single layout or full-width:
  children?: React.ReactNode;
  containerClassName?: string;
}

export const FrameSection: React.FC<FrameSectionProps> = ({
  headline,
  layout = 'twoColumn',
  headlinePosition = 'inline',
  leftContent,
  rightContent,
  fullWidth,
  children,
  containerClassName,
}) => {
  return (
    <section className={containerClassName || 'bg-muted'}>
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="bg-background rounded-xl py-24 md:py-32 px-4 md:px-8">
            {headlinePosition === 'top' && (
              <h2 className="text-4xl md:text-5xl font-bold mb-12 text-foreground text-center">
                {headline}
              </h2>
            )}
            {fullWidth ? (
              <>
                {headlinePosition === 'inline' && (
                  <h2 className="text-4xl md:text-5xl font-bold mb-10 text-foreground text-center">
                    {headline}
                  </h2>
                )}
                {children}
              </>
            ) : layout === 'twoColumn' ? (
              <div className="flex flex-col xl:flex-row gap-12">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-3rem)]">
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      {headlinePosition === 'inline' && (
                        <h2 className="text-4xl md:text-5xl font-bold mb-6 text-foreground w-full">
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
            ) : (
              <div className="text-center">
                {headlinePosition === 'inline' && (
                  <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
                    {headline}
                  </h2>
                )}
                {children}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default FrameSection; 