/**
 * Brand configuration types for white-labeling system
 */

export interface BrandLogoConfig {
  squarePath: string;
  widePath: string;
  narrowPath: string;
  altText?: string;
}

export interface BrandStylesConfig {
  cssPath: string;
}

export interface BrandFaviconConfig {
  faviconPath: string;
}

export interface BrandConfig {
  name: string;
  logo?: BrandLogoConfig;
  styles?: BrandStylesConfig;
  favicon?: BrandFaviconConfig;
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

  // logo is optional, but if present must define all variant paths
  if (cfg.logo !== undefined) {
    if (typeof cfg.logo !== 'object' || cfg.logo === null) {
      return false;
    }
    const logo = cfg.logo as Record<string, unknown>;
    if (typeof logo.squarePath !== 'string' || logo.squarePath.trim() === '') {
      return false;
    }
    if (typeof logo.widePath !== 'string' || logo.widePath.trim() === '') {
      return false;
    }
    if (typeof logo.narrowPath !== 'string' || logo.narrowPath.trim() === '') {
      return false;
    }
    if (logo.altText !== undefined && typeof logo.altText !== 'string') {
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

  // favicon is optional, but if present must have faviconPath
  if (cfg.favicon !== undefined) {
    if (typeof cfg.favicon !== 'object' || cfg.favicon === null) {
      return false;
    }
    const favicon = cfg.favicon as Record<string, unknown>;
    if (typeof favicon.faviconPath !== 'string' || favicon.faviconPath.trim() === '') {
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
