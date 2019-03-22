FROM chilipp/empd-admin-base

ENV TINI_VERSION v0.18.0

USER root

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

# clone the EMPD-tests repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-test.git /opt/empd-admin/empd_admin/data-tests || :

RUN pip install /opt/empd-admin

COPY run-empd-admin-server.sh /usr/local/bin/run-empd-admin-server

# download and verify tini
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/local/bin/tini
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini.asc /tmp/tini.asc
RUN chmod +x /usr/local/bin/tini

RUN gpg --batch --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 595E85A6B1B4779EA4DAAEC70B588DFF0527A9B7 \
 && gpg --batch --verify /tmp/tini.asc /usr/local/bin/tini

USER postgres

ENTRYPOINT ["tini", "--"]

CMD run-empd-admin-server
