# OpenResty Dockerfile für GUSTAV
# Basiert auf OpenResty mit Lua-Support für sichere WebSocket-Authentifizierung

FROM openresty/openresty:1.25.3.1-alpine

# Install additional packages
RUN apk add --no-cache \
    bash \
    curl \
    gettext \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf

# Create necessary directories
RUN mkdir -p /var/log/nginx /var/cache/nginx /var/www/certbot

# Copy nginx configuration template
COPY nginx.conf /etc/nginx/nginx.conf
COPY default-auth-secure.conf /etc/nginx/templates/default.conf.template

# Create entrypoint script for environment variable substitution
RUN printf '#!/bin/bash\nenvsubst "\\$DOMAIN_NAME" < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf\nexec /usr/local/openresty/bin/openresty -g "daemon off;"\n' > /docker-entrypoint.sh \
    && chmod +x /docker-entrypoint.sh

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Run nginx
ENTRYPOINT ["/docker-entrypoint.sh"]