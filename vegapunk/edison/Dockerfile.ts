# Edison's TypeScript test image: Switch Console's workspace dependencies, installed from a locked
# lockfile with lifecycle scripts off (no Electron download, no native builds). The PR's console/
# tree is copied over /deps/console at run time, packages are built, and vitest runs offline.
FROM node:24-bookworm-slim
RUN corepack enable && corepack prepare pnpm@10.28.2 --activate
WORKDIR /deps/console
COPY console/ ./
# low concurrency and a capped heap: this runs beside Edison's test jobs on an 8 GB WSL VM
RUN NODE_OPTIONS=--max-old-space-size=1536 pnpm install --frozen-lockfile --ignore-scripts --network-concurrency 8 --child-concurrency 1
RUN useradd -m -u 1001 runner && chown -R runner /deps
USER runner
