#!/bin/bash
# Test script to simulate Amplify build-time brand asset fetching

set -e  # Exit on error

echo "=== Testing Brand Asset Fetch (Simulating Amplify Build) ==="
echo ""

# Simulate the environment variable
BRAND_ASSETS_URL="${BRAND_ASSETS_URL:-file:///Users/ryan.porter/Projects/Plexus-Capacity-branding/capacity-branding.tar.gz}"

echo "BRAND_ASSETS_URL: $BRAND_ASSETS_URL"
echo ""

# Clean up any existing brands directory
echo "1. Cleaning up existing public/brands directory..."
rm -rf ./public/brands
echo "   ✓ Removed public/brands"
echo ""

# Simulate the amplify.yml preBuild commands
echo "2. Running brand asset fetch (from amplify.yml)..."
if [ ! -z "$BRAND_ASSETS_URL" ]; then
  echo "   Fetching brand assets from $BRAND_ASSETS_URL"
  mkdir -p ./public/brands
  cd ./public/brands
  
  # Check if it's a file:// URL (local testing)
  if [[ $BRAND_ASSETS_URL == file://* ]]; then
    local_path="${BRAND_ASSETS_URL#file://}"
    echo "   Using local file: $local_path"
    cp "$local_path" brands.tar.gz
  else
    echo "   Downloading from remote URL..."
    curl -L -o brands.tar.gz "$BRAND_ASSETS_URL"
  fi
  
  echo "   Extracting tarball..."
  tar -xzf brands.tar.gz
  rm brands.tar.gz
  cd ../..
  echo "   ✓ Brand assets fetched and extracted successfully"
else
  echo "   No BRAND_ASSETS_URL configured, using default branding"
fi
echo ""

# Show what was extracted
echo "3. Verifying extracted contents..."
if [ -d "./public/brands" ]; then
  echo "   Contents of public/brands:"
  ls -la ./public/brands
  echo ""
  if [ -d "./public/brands/capacity" ]; then
    echo "   Contents of public/brands/capacity:"
    ls -la ./public/brands/capacity
  fi
  if [ -d "./public/brands/images" ]; then
    echo ""
    echo "   Contents of public/brands/images:"
    ls -la ./public/brands/images
  fi
else
  echo "   ⚠ public/brands directory not found!"
fi
echo ""

echo "=== Test Complete ==="
echo ""
echo "Next steps:"
echo "1. Set NEXT_PUBLIC_BRAND_CONFIG_URL=/brands/capacity/brand.json in .env.local"
echo "2. Run: npm run dev"
echo "3. Open browser and verify Capacity branding is loaded"

