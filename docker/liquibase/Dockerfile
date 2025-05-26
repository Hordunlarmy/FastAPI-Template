FROM liquibase/liquibase:latest

USER root

COPY docker/liquibase/migrate.sh /usr/local/bin/migrate
RUN chmod +x /usr/local/bin/migrate

USER liquibase
