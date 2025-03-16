# Use an Ubuntu base image with C++ tools
FROM ubuntu:22.04

# Install necessary system packages
RUN apt-get update && apt-get install -y \
    g++ \
    make \
    cmake \
    libssl-dev \
    libjsoncpp-dev \
    liblwip-dev \
    libpthread-stubs0-dev \
    python3 \
    python3-pip \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install ZeroTier SDK (libzt)
RUN wget -O libzt.tar.gz https://github.com/zerotier/libzt/releases/latest/download/libzt-dev-linux-x86_64.tar.gz && \
    mkdir -p /usr/local/libzt && \
    tar -xvzf libzt.tar.gz -C /usr/local/libzt --strip-components=1 && \
    rm libzt.tar.gz && \
    cp /usr/local/libzt/include/* /usr/include/ && \
    cp /usr/local/libzt/lib/*.a /usr/lib/ && \
    ldconfig

# Copy the entire project into the container
COPY . .

# Create build directory and compile C++ file
RUN mkdir -p build && cd build && cmake .. && make -j$(nproc)

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the required port for Flask (Cloud Run requires this)
EXPOSE 8080

# Set entrypoint to start both Flask and Discord bot
CMD ["python3", "discord_bot.py"]
