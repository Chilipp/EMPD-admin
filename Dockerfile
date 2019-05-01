FROM empd2/empd-data

USER root

ADD ./ /opt/empd-admin

RUN /opt/conda/envs/empd-admin/bin/pip install /opt/empd-admin

COPY run-empd-admin-server.sh /usr/local/bin/run-empd-admin-server
COPY docker_tests.sh /usr/local/bin/test-empd-admin

USER postgres

CMD run-empd-admin-server
