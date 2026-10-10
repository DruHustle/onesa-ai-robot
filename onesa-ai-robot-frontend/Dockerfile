FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /build
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY . ./
RUN npm run build
FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1
WORKDIR /app
RUN apk upgrade --no-cache && rm -rf /usr/local/lib/node_modules/npm /opt/yarn-* && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY --chown=node:node server.mjs ./
COPY --from=build --chown=node:node /build/dist ./public
USER node
EXPOSE 3431
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||'3431')+'/').then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.mjs"]
