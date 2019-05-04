/*
 * A small library to implemnt various buttons that send MQTT messages as well
 * as display the state of received messages.
 */

client = new Paho.MQTT.Client(location.hostname, Number(location.port),
  "mqttbuttons-" + (Math.random() * 1000000).toFixed(0));

// set callback handlers
client.onConnectionLost = onConnectionLost;
client.onMessageArrived = onMessageArrived;

// connect the client
client.connect({
 onSuccess: onConnect
});


topics = {}
function onConnect() {
 // Once a connection has been made, make a subscription and send a message.
 console.log("onConnect");
 $(".mqtt-toggle").each(function(i) {
   var element = $(this)
   var topic = element.attr("name")
   console.log("subscribing to " + topic)
   client.subscribe(topic)
   topics[topic] = function(value) {
     element.prop("checked", value == 1)
   }
   element.change(function() {
     msg = new Paho.MQTT.Message(element.prop('checked') ? "1" : "0")
     msg.destinationName = topic
     client.send(msg)
     console.log("sending " + topic + ": " + msg.payloadString)
   })
 })
 $(".mqtt-button").each(function(i) {
   var element = $(this)
   var topic = element.attr("name")
   console.log("posting to " + topic)
   element.on("click", function() {
     msg = new Paho.MQTT.Message(element.prop("value"))
     msg.destinationName = topic
     client.send(msg)
     console.log("sending " + topic + ": " + msg.payloadString)
   })
 })
 // client.subscribe("World");
 // message = new Paho.MQTT.Message("Hello " + new Date());
 // message.destinationName = "World";
 // client.send(message);
}

// called when the client loses its connection
function onConnectionLost(responseObject) {
 if (responseObject.errorCode !== 0) {
   console.log("onConnectionLost:" + responseObject.errorMessage);
 }
}

// called when a message arrives
function onMessageArrived(msg) {
 console.log(msg.destinationName +": " + msg.payloadString);
 if (msg.destinationName in topics) {
   topics[msg.destinationName](msg.payloadString)
 }
}
