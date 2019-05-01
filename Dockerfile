FROM empd2/empd-data

USER root

COPY ./ /opt/empd-admin

RUN /opt/conda/envs/empd-admin/bin/pip install /opt/empd-admin

COPY run-empd-admin-server.sh /usr/local/bin/run-empd-admin-server
COPY run-empd-admin-cli.sh /usr/local/bin/empd-admin
COPY docker_tests.sh /usr/local/bin/test-empd-admin

EXPOSE 5000

USER postgres

CMD run-empd-admin-server
