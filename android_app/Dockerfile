FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV BUILD_HOME=/build

RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libffi-dev \
    libssl-dev \
    autoconf \
    automake \
    libtool \
    pkg-config \
    ccache \
    wget \
    curl \
    unzip \
    zip \
    openjdk-17-jdk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip setuptools virtualenv
RUN pip3 install --upgrade Cython==0.29.36
RUN pip3 install --upgrade buildozer

WORKDIR $BUILD_HOME

COPY . /app

CMD ["buildozer", "-v", "android", "debug"]