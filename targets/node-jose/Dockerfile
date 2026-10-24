FROM node:22.20.0-slim
# Verify that this tag exists and record the confirmed tag in VERSIONS.md.
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY app.js .
EXPOSE 8080
CMD ["node", "app.js"]
