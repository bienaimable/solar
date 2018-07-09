FROM ubuntu:latest
ENV REFRESHED_ON 2018-07-05
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common \
    git \
    python3.7 \
    python3-pip
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    edge"
RUN apt-get update && apt-get install -y docker-ce=18.05.0~ce~3-0~ubuntu
RUN python3.7 -m pip install attrs sh pyyaml Autologging
RUN mkdir /data
WORKDIR /app
COPY moon.py /app
ENTRYPOINT ["python3.7", "moon.py"]


# The docker version in Alpine introduces a bug that prevents the stack from being properly updated
# Using Ubuntu in the meantime
#FROM alpine:3.6
#ENV REFRESHED_ON 2017-09-06
#RUN apk add --update docker
#RUN apk add --update python3
#RUN pip3 install attrs sh pyyaml
#RUN apk add --update git
#WORKDIR /app
#COPY moon.py /app
#ENTRYPOINT ["python3", "moon.py"]
