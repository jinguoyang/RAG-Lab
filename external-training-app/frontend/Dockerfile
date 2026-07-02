FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5183

CMD ["sh", "-c", "npm run dev -- --host 0.0.0.0 --port ${VITE_EXT_TRAINING_FRONTEND_PORT:-5183}"]
