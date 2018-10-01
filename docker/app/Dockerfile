FROM python:slim
MAINTAINER <stb@lassitu.de>

VOLUME /work
WORKDIR /work
COPY Pipfile Pipfile.lock /work/

RUN apt-get update && \
    apt-get install -y gettext libmagic1 build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    ln -fs /usr/lib/python2.7/plat-x86_64-linux-gnu/_sysconfigdata_nd.py /usr/lib/python2.7/ && \
    pip install --upgrade pip && \
    pip install pipenv && \
    pipenv install --dev --deploy --system && \
    rm -rf /root/.cache && \
    find /usr/local -type f -name '*.pyc' -delete
