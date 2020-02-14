FROM python:3.5

RUN apt-get update \
    && apt-get -y upgrade \
    && rm -rf /var/lib/apt/lists/*
#    && apt-get install -y --no-install-recommends \
#    mysql-client \
#    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY ./webapp/requirements3.txt ./requirements.txt
#COPY ./webapp/requirements.txt ./webapp_requirements.txt
#COPY ./services/freshbeats/requirements.txt ./freshbeats_requirements.txt
RUN pip install -r requirements.txt
#RUN pip install -r webapp_requirements.txt
#RUN pip install -r freshbeats_requirements.txt

EXPOSE 8000

VOLUME /music
VOLUME /ssh

COPY ./webapp ./webapp
COPY ./services/freshbeats ./services/freshbeats

WORKDIR /usr/src/app/webapp

#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["gunicorn", "config.wsgi", "-b", "0.0.0.0:8000"]
