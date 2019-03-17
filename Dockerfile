FROM chilipp/empd-admin-base

COPY ./environment.yml /tmp/environment.yml

RUN conda env update -f /tmp/environment.yml -n base && \
    conda clean --yes --all

COPY ./ /opt/empd-admin

# clone the EMPD-tests repository if not existent
RUN git clone https://github.com/EMPD2/EMPD-test.git /opt/empd-admin/empd_admin/data-tests || :

RUN pip install /opt/empd-admin

# delete a file that caused issues in the past (if existent)
RUN rm /opt/conda/lib/python3.7/site-packages/.wh.pip-18.1-py3.7.egg-info || :

CMD python -m empd_admin.webapp
