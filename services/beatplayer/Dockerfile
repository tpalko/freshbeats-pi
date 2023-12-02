ARG ALPINE_ARCH

FROM ${ALPINE_ARCH}/alpine

RUN apk update && apk add --no-cache python3 py3-pip mpv socat jq mariadb-dev build-base python3-dev

WORKDIR /opt/beatplayer 

COPY requirements.txt .
COPY vendor/cowpy ./vendor
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

COPY . .

VOLUME /mnt/music 
EXPOSE ${BEATPLAYER_PORT}

ENV XDG_RUNTIME_DIR=/tmp

WORKDIR /opt/beatplayer/beatplayer

#CMD ["python", "mpplayer.py", "-e", $ENV, "-a", "0.0.0.0", "-p", "9000"]
CMD python3 mpplayer.py -a 0.0.0.0 -p ${BEATPLAYER_PORT}
