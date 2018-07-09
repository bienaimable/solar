#!/bin/bash
# Build from Moon Dockerfile
docker build \
  -t moon \
  . || { echo "Build step failed"; exit 1; }
# Push Moon
docker login || { echo "Login step failed"; exit 1; }
docker tag moon bienaimable/moon2 || { echo "Tagging step failed"; exit 1; }
docker push bienaimable/moon2
