FROM chilipp/empd-admin-base

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

# clone the EMPD-tests repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-test.git /opt/empd-admin/empd_admin/data-tests || :

RUN pip install -U /opt/empd-admin && \
    pip install -U --force-reinstall --no-deps -e /opt/empd-admin

# make all files readable for the user
RUN chmod u+r -R /opt/conda

CMD python -m empd_admin.webapp
