# Plexus Dashboard White-Labeling

This document explains how to white-label the Plexus dashboard with custom branding without modifying the core Plexus codebase.

## Overview

The white-labeling system allows you to:
- Replace the Plexus logo with your own custom logo component
- Override CSS variables (colors, fonts, etc.)
- Keep branding assets in a separate Git repository
- Deploy custom branding alongside the Plexus application

## Architecture

### Separate Branding Repository

Brand assets are stored in a **separate Git repository** (not in the Plexus repo). This keeps the core Plexus codebase clean and allows different deployments to use different branding.

### Configuration Loading

The dashboard loads brand configuration from a URL specified by the environment variable:

```bash
NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/example/brand.json
```

- If the environment variable is not set, the dashboard uses default Plexus branding
- The URL must be same-origin (browser security)
- Configuration is loaded client-side on app startup
- All errors gracefully fall back to default Plexus branding

## Brand Package Structure

A brand package is a directory containing three files:

```
your-brand/
  brand.json       # Configuration file
  logo.js          # Custom logo component (ES module)
  styles.css       # CSS variable overrides
```

### brand.json

The configuration file specifies paths to your custom assets:

```json
{
  "name": "Your Brand Name",
  "logo": {
    "componentPath": "/brands/your-brand/logo.js"
  },
  "styles": {
    "cssPath": "/brands/your-brand/styles.css"
  }
}
```

**Fields:**
- `name` (required): Brand name for identification
- `logo.componentPath` (optional): Path to custom logo ES module
- `styles.cssPath` (optional): Path to CSS file with variable overrides

### logo.js

A simple ES module that exports a React component as the default export:

```javascript
// Simple example - just displays text
export default function CustomLogo({ variant, className }) {
  return (
    <div className={className} style={{ 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      backgroundColor: '#ff6b35',
      color: 'white',
      fontWeight: 'bold',
      fontSize: '1.5em'
    }}>
      ACME
    </div>
  );
}
```

**Component Interface:**

The logo component receives these props:

- `variant`: LogoVariant enum value
  - `LogoVariant.Square` - Square aspect ratio (6x6 grid)
  - `LogoVariant.Wide` - Wide aspect ratio (6x2 grid)
  - `LogoVariant.Narrow` - Narrow aspect ratio (2x2 grid)
- `className` (optional): CSS classes to apply
- `shadowEnabled` (optional): Whether to enable drop shadow
- `shadowWidth` (optional): Shadow blur radius (e.g., "2em")
- `shadowIntensity` (optional): Shadow opacity (0-100)

**Requirements:**
- Must export a default function or component
- Must handle all three variant types
- Must be a valid ES module (no build step required)
- Cannot import external npm packages (unless you build it separately)

**Example with image:**

```javascript
export default function CustomLogo({ variant, className }) {
  // Use different images for different variants
  const imageSrc = variant === 0 ? '/brands/acme/logo-square.svg' :
                   variant === 1 ? '/brands/acme/logo-wide.svg' :
                   '/brands/acme/logo-narrow.svg';
  
  return (
    <div className={className}>
      <img src={imageSrc} alt="ACME" style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
```

### styles.css

Override any CSS variables from `dashboard/app/globals.css`:

```css
/**
 * Custom brand colors
 */

:root {
  /* Primary color (buttons, links, accents) */
  --primary: 25 95% 53%;
  
  /* Secondary color */
  --secondary: 280 85% 60%;
  
  /* Background colors */
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  
  /* Card colors */
  --card: 0 0% 100%;
  --card-foreground: 222.2 84% 4.9%;
  
  /* Muted colors */
  --muted: 210 40% 96.1%;
  --muted-foreground: 215.4 16.3% 46.9%;
  
  /* Accent colors */
  --accent: 210 40% 96.1%;
  --accent-foreground: 222.2 47.4% 11.2%;
  
  /* Destructive colors */
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 210 40% 98%;
  
  /* Border and input colors */
  --border: 214.3 31.8% 91.4%;
  --input: 214.3 31.8% 91.4%;
  --ring: 222.2 84% 4.9%;
  
  /* Chart colors */
  --chart-1: 12 76% 61%;
  --chart-2: 173 58% 39%;
  --chart-3: 197 37% 24%;
  --chart-4: 43 74% 66%;
  --chart-5: 27 87% 67%;
}

.dark {
  /* Dark mode overrides */
  --primary: 25 95% 58%;
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  /* ... etc */
}
```

**Color Format:**

Colors use HSL format without the `hsl()` wrapper:
- Format: `hue saturation% lightness%`
- Example: `220 90% 56%` = hsl(220, 90%, 56%)

**Available Variables:**

See `dashboard/app/globals.css` for the complete list of CSS variables you can override.

## Development Setup

### 1. Create Your Branding Repository

```bash
# Create a new directory for your brand
mkdir -p ~/Projects/YourBrand-plexus-branding
cd ~/Projects/YourBrand-plexus-branding

# Initialize Git
git init

# Create your brand package
mkdir your-brand
cd your-brand

# Create the three required files
touch brand.json logo.js styles.css
```

### 2. Symlink to Plexus Public Directory

For local development, symlink your branding repo into the Plexus dashboard's public directory:

```bash
ln -s ~/Projects/YourBrand-plexus-branding ~/Projects/Plexus/dashboard/public/brands
```

This allows the Next.js dev server to serve your brand files.

### 3. Configure Environment Variable

Create or edit `.env.local` in the dashboard directory:

```bash
cd ~/Projects/Plexus/dashboard
echo 'NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/your-brand/brand.json' >> .env.local
```

### 4. Restart Dev Server

Restart the Next.js development server to pick up the environment variable:

```bash
# The dev server should already be running
# Just restart it to load the new environment variable
```

### 5. Verify in Browser

Open the browser console and look for these messages:

```
[BrandProvider] Loading brand config from: /brands/your-brand/brand.json
[BrandProvider] Fetched brand config: {name: "Your Brand", ...}
[BrandProvider] Brand config validated successfully
[BrandProvider] Injecting custom CSS from: /brands/your-brand/styles.css
[BrandProvider] Loading custom logo component from: /brands/your-brand/logo.js
[BrandProvider] Custom logo component loaded successfully
```

## Production Deployment

### 1. Deploy Branding Repository

Deploy your branding repository contents to your web server at the `/brands/` path:

```bash
# Example: Copy to web server
scp -r ~/Projects/YourBrand-plexus-branding/* user@server:/var/www/plexus/brands/

# Or use your deployment pipeline
```

### 2. Set Environment Variable

Configure the environment variable in your production environment:

```bash
NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/your-brand/brand.json
```

**Important:** Next.js environment variables are baked into the build at build time. You must:
1. Set the environment variable before building
2. Rebuild the application if you change the environment variable

### 3. Build and Deploy Plexus

```bash
cd ~/Projects/Plexus/dashboard
npm run build
# Deploy the built application
```

## Error Handling

The white-labeling system is designed to gracefully handle all errors:

### Configuration Loading Errors

If `brand.json` fails to load or is invalid:
- Console error is logged
- Dashboard uses default Plexus branding
- Application continues to function normally

### CSS Loading Errors

If `styles.css` fails to load:
- Console error is logged
- Dashboard uses default Plexus styles
- Application continues to function normally

### Logo Component Errors

If `logo.js` fails to load or crashes during rendering:
- Error is caught by React Error Boundary
- Console error is logged
- Dashboard falls back to default Plexus logo
- Application continues to function normally

## Testing Your Brand

### Test Checklist

1. **Logo Variants**
   - [ ] Square logo displays correctly in dashboard sidebar (collapsed)
   - [ ] Wide logo displays correctly in dashboard sidebar (expanded)
   - [ ] Narrow logo displays correctly in mobile header
   - [ ] Logo displays correctly on landing page
   - [ ] Logo displays correctly in documentation pages

2. **Colors**
   - [ ] Primary color appears correctly in buttons and links
   - [ ] Secondary color appears correctly in accents
   - [ ] Colors work correctly in light mode
   - [ ] Colors work correctly in dark mode
   - [ ] All interactive elements are visible and accessible

3. **Responsive Design**
   - [ ] Branding works on desktop (1920x1080)
   - [ ] Branding works on tablet (768x1024)
   - [ ] Branding works on mobile (375x667)

4. **Error Scenarios**
   - [ ] App works if brand.json is missing (uses default branding)
   - [ ] App works if logo.js is missing (uses default logo)
   - [ ] App works if styles.css is missing (uses default styles)
   - [ ] App works if logo.js has syntax error (falls back to default)

## Example Brand Package

See the example brand in the separate branding repository:
- Repository: `~/Projects/Plexus-branding`
- Example package: `example/`

The example demonstrates:
- Simple text-based logo
- Orange primary color override
- Proper brand.json structure

## Troubleshooting

### Brand not loading

**Check console for errors:**
```
[BrandProvider] No NEXT_PUBLIC_BRAND_CONFIG_URL specified, using default branding
```
→ Environment variable not set. Add to `.env.local` and restart dev server.

**Check console for 404 errors:**
```
Failed to fetch brand config: 404 Not Found
```
→ Brand files not accessible. Check symlink or file paths.

### Logo not displaying

**Check console for import errors:**
```
[BrandProvider] Failed to load custom logo component: ...
```
→ Check logo.js syntax. Must be valid ES module with default export.

**Logo component crashes:**
→ Check browser console for React errors. Error boundary will fall back to default logo.

### Colors not applying

**Check if CSS file is loading:**
→ Open browser DevTools → Network tab → Look for styles.css request

**Check CSS variable format:**
→ Must use format `220 90% 56%` not `hsl(220, 90%, 56%)`

### Environment variable not working

**Next.js caches environment variables:**
→ Must restart dev server after changing `.env.local`

**Production environment:**
→ Must rebuild application after changing environment variable

## Security Considerations

### Same-Origin Policy

Brand assets must be served from the same origin as the Plexus dashboard. This is enforced by browser security (CORS).

**Good:**
- `NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/acme/brand.json`

**Bad:**
- `NEXT_PUBLIC_BRAND_CONFIG_URL=https://external-site.com/brand.json` (CORS error)

### Code Execution

The `logo.js` file is executed as JavaScript in the browser. Only load logo components from trusted sources.

**Best Practice:**
- Keep branding repository in your own infrastructure
- Review logo.js code before deployment
- Use Content Security Policy (CSP) headers if needed

## Advanced: Building Custom Logo Components

If you need to use external npm packages or TypeScript in your logo component, you'll need to build it separately:

### Option 1: Simple Build Script

```javascript
// build-logo.js
import esbuild from 'esbuild';

esbuild.build({
  entryPoints: ['src/logo.tsx'],
  bundle: true,
  outfile: 'dist/logo.js',
  format: 'esm',
  external: ['react', 'react-dom'],
  jsx: 'automatic',
});
```

### Option 2: Full Build System

Create a separate project with its own `package.json` and build system. This is covered in a separate guide (not yet implemented).

## Support

For questions or issues:
1. Check this documentation
2. Review the example brand package
3. Check browser console for error messages
4. Contact the Plexus team

