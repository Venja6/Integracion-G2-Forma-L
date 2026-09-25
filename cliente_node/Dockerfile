FROM node:22-slim

WORKDIR /app

COPY package.json .
RUN npm install --omit=dev

COPY cliente.js .
# Mismo contrato que usa el servidor, no una copia
COPY --from=flota_contrato flota.proto ./proto/flota.proto

CMD ["node", "cliente.js"]
