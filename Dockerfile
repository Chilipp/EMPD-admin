FROM chilipp/empd-admin-base

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

RUN pip install -U /opt/empd-admin && \
    pip install -U --force-reinstall --no-deps -e /opt/empd-admin

CMD python -m empd_admin.webapp
