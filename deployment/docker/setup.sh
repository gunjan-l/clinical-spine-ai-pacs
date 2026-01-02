#!/bin/bash
# Setup script for clinical spine AI pipeline

set -e

echo "🚀 Setting up Clinical Spine AI PACS repository..."

# 1. Initialize TotalSpineSeg submodule
echo "📦 Initializing TotalSpineSeg submodule..."
git submodule init
git submodule update

# 2. Verify dcm2niix installation
echo "🔍 Checking dcm2niix..."
if ! command -v dcm2niix &> /dev/null; then
    echo "dcm2niix not found. Installing..."
    # Update and install with -y to avoid prompts
    sudo apt-get update && sudo apt-get install -y dcm2niix
else
    echo "dcm2niix verified."
fi

# 3. Verify itkimage2segimage (DCMQI)
echo "🔍 Checking itkimage2segimage..."
if ! command -v itkimage2segimage &> /dev/null; then
    echo "itkimage2segimage not found. Downloading dcmqi..."

    # Define version
    DCMQI_VER="1.4.0"
    DCMQI_FILE="dcmqi-${DCMQI_VER}-linux.tar.gz"
    DCMQI_URL="https://github.com/QIICR/dcmqi/releases/download/v${DCMQI_VER}/${DCMQI_FILE}"

    # Download using standard wget
    wget -q "$DCMQI_URL"

    # Unzip the archive
    tar -xzvf "$DCMQI_FILE" > /dev/null

    # Add the 'bin' directory to the system PATH for this session
    # We use $(pwd) to get the current absolute path
    export PATH="$PATH:$(pwd)/dcmqi-${DCMQI_VER}-linux/bin"

    # Clean up the tar file to keep folder clean
    rm "$DCMQI_FILE"

    echo "Temporarily added dcmqi to PATH."
fi

# Verify that the command is now available
if ! command -v itkimage2segimage &> /dev/null; then
    echo "❌ Error: itkimage2segimage failed to install or is not in PATH."
    exit 1
else
    echo "itkimage2segimage verified."
fi

# 4. Build Docker image
echo "🐳 Building TotalSpineSeg Docker image..."
# Using the custom file name as discussed
docker build -f deployment/docker/totalspineseg.Dockerfile -t clinical-spine-ai:latest .

echo "✅ Setup complete!"
echo "📖 Next steps: See docs/deployment_guide.md"