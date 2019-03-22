FROM chilipp/empd-admin-base

ENV TINI_VERSION v0.18.0

USER root

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

# clone the EMPD-tests repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-test.git /opt/empd-admin/empd_admin/data-tests || :

# clone the EMPD-data repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-data.git /opt/empd-admin/empd_admin/data || :

RUN pip install /opt/empd-admin

COPY run-empd-admin-server.sh /usr/local/bin/run-empd-admin-server

# download and verify tini
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/local/bin/tini
RUN chmod +x /usr/local/bin/tini

USER postgres

ENTRYPOINT ["tini", "--"]

CMD run-empd-admin-server
