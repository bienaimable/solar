FROM ubuntu:xenial
ENV REFRESHED_ON 2017-11-20
RUN apt-get update && apt-get install -y \
    linux-image-extra-$(uname -r) \
    linux-image-extra-virtual \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common \
    git \
    python3 \
    python3-pip
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"
RUN apt-get update && apt-get install -y docker-ce=17.09.0~ce-0~ubuntu
RUN pip3 install attrs sh pyyaml Autologging
WORKDIR /app
COPY moon.py /app
ENTRYPOINT ["python3", "moon.py"]


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
