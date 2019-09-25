FROM python:2.7

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    mysql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY ./webapp/requirements.txt ./webapp_requirements.txt
COPY ./services/freshbeats/requirements.txt ./freshbeats_requirements.txt
RUN pip install -r webapp_requirements.txt
RUN pip install -r freshbeats_requirements.txt

EXPOSE 8000

ENV FRESHBEATS_DATABASE_HOST=frankdb_mysql
ENV FRESHBEATS_SWITCHBOARD_EXTERNAL_HOST=switchboard.freshbeats.palkosoftware.ddns.net
ENV FRESHBEATS_SWITCHBOARD_INTERNAL_HOST=freshbeats_switchboard
ENV FRESHBEATS_SWITCHBOARD_EXTERNAL_PORT=80
ENV FRESHBEATS_SWITCHBOARD_INTERNAL_PORT=3333
ENV FRESHBEATS_MUSIC_PATH=/music

VOLUME /music
VOLUME /ssh

COPY ./webapp ./webapp
COPY ./services/freshbeats ./services/freshbeats

WORKDIR /usr/src/app/webapp

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
