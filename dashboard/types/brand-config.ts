/**
 * Brand configuration types for white-labeling system
 */

export interface BrandLogoConfig {
  componentPath: string;
}

export interface BrandStylesConfig {
  cssPath: string;
}

export interface BrandConfig {
  name: string;
  logo?: BrandLogoConfig;
  styles?: BrandStylesConfig;
}

/**
 * Validates a brand configuration object
 */
export function validateBrandConfig(config: unknown): config is BrandConfig {
  if (!config || typeof config !== 'object') {
    return false;
  }

  const cfg = config as Record<string, unknown>;

  // name is required
  if (typeof cfg.name !== 'string' || cfg.name.trim() === '') {
    return false;
  }

  // logo is optional, but if present must have componentPath
  if (cfg.logo !== undefined) {
    if (typeof cfg.logo !== 'object' || cfg.logo === null) {
      return false;
    }
    const logo = cfg.logo as Record<string, unknown>;
    if (typeof logo.componentPath !== 'string' || logo.componentPath.trim() === '') {
      return false;
    }
  }

  // styles is optional, but if present must have cssPath
  if (cfg.styles !== undefined) {
    if (typeof cfg.styles !== 'object' || cfg.styles === null) {
      return false;
    }
    const styles = cfg.styles as Record<string, unknown>;
    if (typeof styles.cssPath !== 'string' || styles.cssPath.trim() === '') {
      return false;
    }
  }

  return true;
}

/**
 * Type guard to check if a value is a valid BrandConfig
 */
export function isBrandConfig(value: unknown): value is BrandConfig {
  return validateBrandConfig(value);
}

