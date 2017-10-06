FROM alpine:3.6
ENV REFRESHED_ON 2017-09-06
RUN apk add --update docker
RUN apk add --update python3
RUN pip3 install attrs sh pyyaml
RUN apk add --update git
WORKDIR /app
COPY moon.py /app
ENTRYPOINT ["python3", "moon.py"]
