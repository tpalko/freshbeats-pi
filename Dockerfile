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
COPY ./webapp ./webapp
COPY ./services/freshbeats ./services/freshbeats

EXPOSE 8000

#ENV DJANGO_DATABASE=docker
WORKDIR /usr/src/app/webapp
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
