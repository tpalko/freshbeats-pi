FROM python:3

RUN apt-get -y update && apt-get -y upgrade

WORKDIR /opt/beatplayer 

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

VOLUME /mnt/music 
EXPOSE 9000

ARG ENV
ENV ENV ${ENV}

#CMD ["python", "mpplayer.py", "-e", $ENV, "-a", "0.0.0.0", "-p", "9000"]
CMD python mpplayer.py -e ${ENV} -a 0.0.0.0 -p 9000
