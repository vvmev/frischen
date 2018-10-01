# frischen
A loosely coupled set of components for (simulated) signal towers

## Run Mosquitto Broker

Make sure you have a working setup of Docker Compose. Then simply `docker-compose up` to start up the broker.

The broker configration is in [mosquitto/config/mosquitto.conf](mosquitto/config/mosquitto.conf).  The broker will be listening on localhost on port 1883 (MQTT, no TLS) and 9001 (Websocket, no TLS).
