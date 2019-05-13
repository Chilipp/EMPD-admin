FROM empd2/empd-admin:latest

USER root

RUN conda install -n empd-admin -c conda-forge sphinx sphinx-argparse \
    autodocsumm sphinx_bootstrap_theme ipython pandoc sphinxcontrib-programoutput

COPY . /opt/empd-admin/docs

RUN chmod -R 0777 /opt/empd-admin/docs

RUN cp /opt/empd-admin/docs/build-docker-docs.sh /usr/local/bin/build-empd-admin-docs

USER postgres
