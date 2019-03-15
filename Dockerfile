FROM chilipp/empd-admin-base

ADD ./ /opt/empd-admin

ADD ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

RUN pip install /opt/empd-admin

CMD python -m empd_admin.webapp
