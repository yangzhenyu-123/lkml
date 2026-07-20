FROM alpine/git:latest

RUN apk add --no-cache bash curl

WORKDIR /app
COPY init-and-fetch.sh /app/init-and-fetch.sh
RUN chmod +x /app/init-and-fetch.sh

VOLUME ["/git"]
ENTRYPOINT ["/app/init-and-fetch.sh"]
