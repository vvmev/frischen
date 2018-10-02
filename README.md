# frischen
A loosely coupled set of components for (simulated) signal towers

## Run Mosquitto Broker

Make sure you have a working setup of Docker Compose. Then simply `docker-compose up` to start up the broker.

The broker configuration is in [mosquitto/config/mosquitto.conf](mosquitto/config/mosquitto.conf).  The broker will be listening on localhost on port 1883 (MQTT, no TLS) and 9001 (Websocket, no TLS).

## Applications

### Python

Use [pipenv](https://pipenv.readthedocs.io/en/latest/) to set up your local Python environment.

Simple Python apps have a single file in the top level diretory.

### Web

Web apps are used together with MQTT over Websockets for general visualization and to build graphical user interfaces. These live in [web/](./web). You can browse them at [localhost:9001](http://localhost:9001/).

## Links and Documentation

* Eclipse Mosquitto [Project](https://projects.eclipse.org/projects/technology.mosquitto), [Mosquitto Docker Image](https://hub.docker.com/_/eclipse-mosquitto/)
* Eclipse Paho [Project](https://www.eclipse.org/paho/), [Python client](https://www.eclipse.org/paho/clients/python/), [JavaScript client](https://www.eclipse.org/paho/clients/js/)
* [Docker Compose](https://docs.docker.com/compose/overview/)
