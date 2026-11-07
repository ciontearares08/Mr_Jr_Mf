# Change base image from trixie to bookworm to support older APSIM dependencies
FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm AS dev

ARG APSIM_VERSION="8110"

# 1. Add Microsoft's Bookworm repository (required to fetch .NET 6)
# 2. Download and install APSIM (apt-get will now successfully find .NET 6 and gtk-sharp3)
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y wget ca-certificates apt-transport-https gnupg \
    && wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && wget -O apsim.deb "https://builds.apsim.info/api/nextgen/download/${APSIM_VERSION}/Linux" \
    && apt-get install -y ./apsim.deb \
    && rm apsim.deb \
    && ln -s /usr/local/lib/apsim/*/bin /opt/apsim \
    && test -x /opt/apsim/Models \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# APSIM bin folder, read by apsim_models_path() in the sim service
ENV APSIM_BIN_PATH=/opt/apsim

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /workspace/apps/sim