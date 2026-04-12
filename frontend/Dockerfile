ARG NODE_BASE_IMAGE=node:24-alpine
FROM ${NODE_BASE_IMAGE}

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend /app/frontend
RUN npm run build
EXPOSE 4173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]
