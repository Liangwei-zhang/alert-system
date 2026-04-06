FROM postgres:16-alpine

RUN apk add --no-cache pgbouncer gettext \
    && mkdir -p /etc/pgbouncer \
    && chown -R postgres:postgres /etc/pgbouncer

COPY pgbouncer.ini.template /etc/pgbouncer/pgbouncer.ini.template
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER postgres

EXPOSE 6432

CMD ["/usr/local/bin/docker-entrypoint.sh"]