# Multi-stage Dockerfile for TotalSpineSeg Clinical Deployment
# Optimized for production spine segmentation pipeline

# ============================================================================
# BUILD STAGE 1: Base environment with CUDA and Python
# ============================================================================
FROM nvidia/cuda:11.8-devel-ubuntu20.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TOTALSPINESEG_DATA=/app/models

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    python3-pip \
    git \
    wget \
    build-essential \
    cmake \
    libgdcm-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# ============================================================================
# BUILD STAGE 2: Install TotalSpineSeg and dependencies
# ============================================================================
FROM base AS builder

ENV PATH="/opt/venv/bin:$PATH"

# Install PyTorch with CUDA support
RUN pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu118

# Install TotalSpineSeg from PyPI (stable for production)
RUN pip install totalspineseg[nnunetv2]==1.0.0

# Install additional medical imaging tools
RUN pip install \
    simpleitk >=2.0.0 \
    pydicom >=2.3.0 \
    nibabel >=3.0.0 \
    numpy >=1.21.0

# Download pre-trained models (automated)
RUN python -c "from totalspineseg import download_models; download_models()"

# ============================================================================
# BUILD STAGE 3: Runtime image (minimize size)
# ============================================================================
FROM nvidia/cuda:11.8-runtime-ubuntu20.04 AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    python3.10 \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy models
COPY --from=builder /app/models /app/models
ENV TOTALSPINESEG_DATA=/app/models

# Create app directory
WORKDIR /app

# Copy application code
COPY ai-pipeline/ ./ai-pipeline/
COPY config/ ./config/

# Create directories for processing
RUN mkdir -p /app/input /app/output /app/logs

# Set permissions
RUN chmod +x ai-pipeline/inference/spine_segmentation.py

# ============================================================================
# FINAL CONFIGURATION
# ============================================================================

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import totalspineseg; print('TotalSpineSeg ready')" || exit 1

# Default command
CMD ["python", "ai-pipeline/inference/spine_segmentation.py", "--help"]

# Labels
LABEL maintainer="Spine AI Segmentation"
LABEL description="Clinical TotalSpineSeg deployment for spine segmentation"
LABEL version="1.0.0-production"