FROM chilipp/empd-admin-base

ADD ./ /opt/empd-admin

RUN conda install --yes python=3.7 --file conda-requirements.txt && \
    conda clean --yes --all

RUN pip install /opt/empd-admin

CMD python -m empd_admin.webapp
