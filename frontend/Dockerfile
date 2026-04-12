ARG NODE_BASE_IMAGE=node:24-alpine
FROM ${NODE_BASE_IMAGE}

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm config set replace-registry-host always \
    && npm ci --registry "${NPM_REGISTRY}"
COPY frontend /app/frontend
RUN npm run build
EXPOSE 4173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]
