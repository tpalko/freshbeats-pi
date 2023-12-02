FROM node:latest

RUN apt-get -y update \
  && apt-get -y upgrade \
  && apt-get -y install yarn

WORKDIR /app

COPY package.json /app

RUN yarn

EXPOSE 3333

COPY . /app

CMD ["node", "switchboard.js"]
