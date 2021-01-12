FROM alpine

#Install gcc
RUN apk add --update alpine-sdk

#Install python and packages
RUN apk add --update --no-cache python3-dev && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

RUN pip3 install dropbox

#Workdir and files
WORKDIR /app/
COPY ./Dockerfile ./Dockerfile
COPY ./dropbox-sync.py ./dropbox-sync.py
COPY ./README.md ./README.md

RUN mkdir /Dropbox

#Start syncing
CMD ["python3", "dropbox-sync.py", "/Dropbox", "/", "-v"]

#docker run -it -v $(pwd)/Dropbox:/Dropbox imxdev/dropbox-sync
