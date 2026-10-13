# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Container image of FAIR-bioHeaders Tools, for workflow managers such as
# Nextflow. It installs the fair-bioheaders wheel in dist/ (the released wheel
# in the container workflow; `poetry build -f wheel` locally) with --no-deps on
# top of the hash-locked runtime dependencies in docker/requirements.txt.
#
#   poetry build -f wheel
#   docker build -t fair-bioheaders .
#
# There is no ENTRYPOINT, because Nextflow runs task scripts with bash; give the
# command, for example `docker run --rm fair-bioheaders bioheaders --help`.

FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f

ARG VERSION=unknown
LABEL org.opencontainers.image.title="fair-bioheaders" \
      org.opencontainers.image.description="Validate, convert, combine and strip FAIR-bioHeaders metadata" \
      org.opencontainers.image.source="https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools" \
      org.opencontainers.image.documentation="https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools#container-image" \
      org.opencontainers.image.licenses="MPL-2.0" \
      org.opencontainers.image.version="${VERSION}"

# procps provides ps, which Nextflow uses to collect task metrics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements.txt /tmp/requirements.txt
COPY dist/ /tmp/dist/
RUN set -eu; \
    wheels="$(ls /tmp/dist/fair_bioheaders-*-py3-none-any.whl)"; \
    test "$(echo "$wheels" | wc -l)" -eq 1; \
    python -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt; \
    python -m pip install --no-cache-dir --no-deps "$wheels"; \
    python -m pip check; \
    if [ "$VERSION" != unknown ]; then test "$(bioheaders --version)" = "$VERSION"; fi; \
    rm -rf /tmp/requirements.txt /tmp/dist

RUN useradd --create-home --uid 1000 bioheaders
USER bioheaders
WORKDIR /home/bioheaders
CMD ["bioheaders", "--help"]
