FROM chilipp/empd-admin-base

ADD ./ /opt/empd-admin

ADD ./conda-requirements.txt /tmp/conda-requirements.txt

RUN conda install --yes python=3.7 --file /tmp/conda-requirements.txt && \
    conda clean --yes --all

RUN pip install /opt/empd-admin

CMD python -m empd_admin.webapp
