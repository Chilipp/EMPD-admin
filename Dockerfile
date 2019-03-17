FROM chilipp/empd-admin-base

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

# clone the EMPD-tests repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-test.git /opt/empd-admin/empd_admin/data-tests || :

RUN pip install /opt/empd-admin

RUN conda create --yes -p /opt/test-env pytest pandas sqlalchemy psycopg2 shapely netcdf4 && /
    pip install latlon-utils && \
    conda clean --yes --all

USER empd-admin
CMD python -m empd_admin.webapp
