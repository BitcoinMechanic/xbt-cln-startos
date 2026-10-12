# Full patched engine, including native REST, gRPC and ordinary node plugins.
FROM rust:1.92.0-bookworm AS engine
ARG BUILD_JOBS=8
ENV CARGO_BUILD_JOBS=4 PYTHON=python3 PYTEST=""
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential ca-certificates gettext git jq libgmp-dev \
    libpq-dev libsodium-dev libsqlite3-dev libssl-dev libtool lowdown pkg-config \
    protobuf-compiler python3 python3-mako zlib1g-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init && git remote add origin https://github.com/BitcoinMechanic/lightning.git && \
    git fetch --depth=1 origin ddd89e1d70d0ba415880a0ff02db7b053c73a298 && \
    git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD^{tree})" = 21369587e10687c21634ec2b1d15a5de6db09496 && \
    git submodule update --init --recursive
RUN ./configure --prefix=/usr/local --enable-rust --disable-valgrind && \
    make -j"${BUILD_JOBS}" install-program DESTDIR=/dist RUST_PROFILE=release \
      VERSION=v26.06.9-blake2b.7-swap0086

FROM debian:bookworm-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
FROM base AS bitcoin-cli
ARG TARGETARCH
ARG BITCOIN_VERSION=27.1
ARG BITCOIN_SHA256_AMD64=c9840607d230d65f6938b81deaec0b98fe9cb14c3a41a5b13b2c05d044a48422
ARG BITCOIN_SHA256_ARM64=bb878df4f8ff8fb8acfb94207c50f959c462c39e652f507c2a2db20acc6a1eee
RUN apt-get update -qq && \
    apt-get install -qq -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*
RUN set -eu; \
    case "$TARGETARCH" in \
      amd64) SHA="$BITCOIN_SHA256_AMD64"; ARCH=x86_64 ;; \
      arm64) SHA="$BITCOIN_SHA256_ARM64"; ARCH=aarch64 ;; \
      *) echo "unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    TARBALL="bitcoin-${BITCOIN_VERSION}-${ARCH}-linux-gnu.tar.gz"; \
    curl -fsSLO "https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/${TARBALL}"; \
    echo "${SHA}  ${TARBALL}" | sha256sum -c -; \
    tar -xf "$TARBALL" "bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli"; \
    install -m 755 "bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli" /usr/bin/bitcoin-cli


FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libgmp10 libpq5 libsodium23 libsqlite3-0 libssl3 libstdc++6 zlib1g python3 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=engine /dist/usr/local/ /usr/local/
COPY --from=bitcoin-cli /usr/bin/bitcoin-cli /usr/bin/bitcoin-cli
# Bundled separately: no swap plugin discovery or mainnet activation.
COPY --from=engine /src/tools/swap/ /usr/local/libexec/xbt-swap/
COPY --from=engine /src/LICENSE /usr/local/share/xbt-cln/LICENSE
COPY assets/source-lock.json /usr/local/share/xbt-cln/source-lock.json
RUN lightningd --version && \
    test -x /usr/local/libexec/c-lightning/plugins/clnrest && \
    test -x /usr/local/libexec/c-lightning/plugins/cln-grpc && \
    test -x /usr/local/libexec/c-lightning/plugins/cln-askrene && \
    test -x /usr/local/libexec/c-lightning/plugins/pay && \
    test -x /usr/local/libexec/c-lightning/plugins/bookkeeper && \
    test -x /usr/local/libexec/c-lightning/plugins/sql
CMD ["lightningd", "--version"]
