import React, { Component, ReactNode } from 'react';
import SquareLogo, { LogoVariant } from './logo-square';

interface LogoErrorBoundaryProps {
  children: ReactNode;
  variant: LogoVariant;
  className?: string;
  shadowEnabled?: boolean;
  shadowWidth?: string;
  shadowIntensity?: number;
}

interface LogoErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary that catches errors from custom logo rendering
 * and falls back to the default Plexus logo
 */
class LogoErrorBoundary extends Component<LogoErrorBoundaryProps, LogoErrorBoundaryState> {
  constructor(props: LogoErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): LogoErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[LogoErrorBoundary] Custom logo component failed to render:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Fallback to default Plexus logo
      console.log('[LogoErrorBoundary] Falling back to default logo');
      return (
        <SquareLogo
          variant={this.props.variant}
          className={this.props.className}
          shadowEnabled={this.props.shadowEnabled}
          shadowWidth={this.props.shadowWidth}
          shadowIntensity={this.props.shadowIntensity}
        />
      );
    }

    return this.props.children;
  }
}

export default LogoErrorBoundary;

