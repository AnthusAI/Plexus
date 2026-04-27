# Plexus Dashboard White-Labeling

This document explains how to white-label the Plexus dashboard with custom branding without modifying the core Plexus codebase.

## Overview

The white-labeling system allows you to:
- Replace the Plexus logo with your own static logo assets
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
  logo-square.svg  # Square logo asset
  logo-wide.svg    # Wide logo asset
  logo-narrow.svg  # Narrow logo asset
  styles.css       # CSS variable overrides
```

### brand.json

The configuration file specifies paths to your custom assets:

```json
{
  "name": "Your Brand Name",
  "logo": {
    "squarePath": "/brands/your-brand/logo-square.svg",
    "widePath": "/brands/your-brand/logo-wide.svg",
    "narrowPath": "/brands/your-brand/logo-narrow.svg",
    "altText": "Your Brand logo"
  },
  "styles": {
    "cssPath": "/brands/your-brand/styles.css"
  }
}
```

**Fields:**
- `name` (required): Brand name for identification
- `logo.squarePath` (optional): Path to square logo image
- `logo.widePath` (optional): Path to wide logo image
- `logo.narrowPath` (optional): Path to narrow logo image
- `logo.altText` (optional): Accessible alt text for logo images
- `styles.cssPath` (optional): Path to CSS file with variable overrides

### Logo Assets

Provide three image files for the dashboard logo variants:

- `logo-square.svg` for square contexts
- `logo-wide.svg` for wide headers/navigation
- `logo-narrow.svg` for compact sidebars

Use SVG when possible for crisp rendering at all sizes.

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

# Create the required files
touch brand.json logo-square.svg logo-wide.svg logo-narrow.svg styles.css
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

Open the browser devtools and verify:

```
[BrandProvider] Loading brand config from: /brands/your-brand/brand.json
[BrandProvider] Fetched brand config: {name: "Your Brand", ...}
[BrandProvider] Brand config validated successfully
[BrandProvider] Injecting custom CSS from: /brands/your-brand/styles.css
- `brand.json` is fetched successfully
- `styles.css` is fetched successfully
- logo asset paths in `brand.json` return 200
```

## Production Deployment

### AWS Amplify Deployment

For AWS Amplify deployments, brand assets are automatically fetched and bundled during the build process. This ensures assets are served from the same origin (required for security).

#### Step 1: Package Your Brand Assets

Create a tarball of your brand repository:

```bash
cd /path/to/your-branding-repo
tar -czf brand-assets.tar.gz capacity/ images/
```

The tarball should contain your brand directories with their files:
```
capacity/
  brand.json
  logo-square.svg
  logo-wide.svg
  logo-narrow.svg
  styles.css
images/
  capacity-logo.png
```

#### Step 2: Host the Tarball

Upload the tarball to any accessible HTTPS endpoint:

**Option A: GitHub Releases**
1. Create a release in your branding repository
2. Attach the tarball as a release asset
3. Use the release asset URL

**Option B: Existing S3 Bucket**
```bash
aws s3 cp brand-assets.tar.gz s3://your-bucket/brands/
aws s3 presign s3://your-bucket/brands/brand-assets.tar.gz --expires-in 604800
```

**Option C: Any CDN or Web Server**
- Upload to CloudFront, Cloudflare, or any HTTPS endpoint
- Ensure the URL is accessible during build time

#### Step 3: Configure Amplify Environment Variables

In the AWS Amplify Console (App Settings → Environment Variables), set:

```bash
BRAND_ASSETS_URL=https://your-cdn.com/brand-assets.tar.gz
NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/capacity/brand.json
```

- `BRAND_ASSETS_URL`: URL to your tarball (fetched during build)
- `NEXT_PUBLIC_BRAND_CONFIG_URL`: Path to brand.json (used by browser)

#### Step 4: Deploy

The next Amplify build will automatically:
1. Download the tarball from `BRAND_ASSETS_URL`
2. Extract it into `public/brands/`
3. Build the Next.js app with the brand assets included
4. Deploy the app with branding baked in

#### Updating Branding

To update branding without code changes:
1. Create a new tarball with updated assets
2. Upload to a new URL (or replace the existing one)
3. Update `BRAND_ASSETS_URL` in Amplify Console
4. Trigger a new build

**Note:** Brand assets are baked into the build. Updates require a rebuild.

### Manual/Self-Hosted Deployment

If you're not using AWS Amplify, deploy your branding repository contents to your web server at the `/brands/` path:

```bash
# Example: Copy to web server
scp -r ~/Projects/YourBrand-plexus-branding/* user@server:/var/www/plexus/brands/

# Or use your deployment pipeline
```

Then set the environment variable before building:

```bash
NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/your-brand/brand.json
npm run build
```

**Important:** Next.js environment variables are baked into the build at build time. You must rebuild if you change the environment variable.

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

### Logo Asset Errors

If a configured logo asset path is missing:
- Browser logs a 404 for that asset
- The logo image will not render for that variant
- Application shell and routing continue to function normally

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
   - [ ] App works if a configured logo image path is missing
   - [ ] App works if styles.css is missing (uses default styles)

## Example Brand Package

See the example brand in the separate branding repository:
- Repository: `~/Projects/Plexus-branding`
- Example package: `example/`

The example demonstrates:
- Static image logo variants
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

**Check network for asset errors:**
→ Verify `squarePath`, `widePath`, and `narrowPath` are valid URLs in `brand.json`.

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

### Static Assets Only

Logo branding uses static image files only (SVG/PNG/WebP). JavaScript logo modules are intentionally unsupported to avoid runtime incompatibilities.

## Support

For questions or issues:
1. Check this documentation
2. Review the example brand package
3. Check browser console for error messages
4. Contact the Plexus team
