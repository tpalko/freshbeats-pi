FROM arm32v6/alpine

RUN apk update && apk add --no-cache python3 py3-pip mpv socat

WORKDIR /opt/beatplayer 

COPY requirements.txt .

RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

COPY . .

VOLUME /mnt/music 
EXPOSE 9000

ENV XDG_RUNTIME_DIR=/tmp

#CMD ["python", "mpplayer.py", "-e", $ENV, "-a", "0.0.0.0", "-p", "9000"]
CMD python3 mpplayer.py -a 0.0.0.0 -p 9000
