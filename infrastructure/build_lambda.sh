#!/bin/bash
# Build Lambda function packages
# This script creates a clean build directory with source files and dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
LAMBDA_FUNCTIONS_DIR="$SCRIPT_DIR/lambda_functions"

echo "Building Lambda functions..."

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build each Lambda function
for function_dir in "$LAMBDA_FUNCTIONS_DIR"/*; do
    if [ -d "$function_dir" ]; then
        function_name=$(basename "$function_dir")
        echo ""
        echo "Building $function_name..."
        
        # Create build directory for this function
        function_build_dir="$BUILD_DIR/$function_name"
        mkdir -p "$function_build_dir"
        
        # Copy source files (Python files, not dependencies)
        echo "  Copying source files..."
        cp "$function_dir"/*.py "$function_build_dir/" 2>/dev/null || true
        cp "$function_dir"/*.md "$function_build_dir/" 2>/dev/null || true
        
        # Install dependencies if requirements.txt exists
        if [ -f "$function_dir/requirements.txt" ]; then
            echo "  Installing dependencies..."
            pip install -r "$function_dir/requirements.txt" -t "$function_build_dir" --upgrade --quiet
        fi
        
        echo "  ✓ Built $function_name"
    fi
done

echo ""
echo "✓ All Lambda functions built successfully in $BUILD_DIR"

