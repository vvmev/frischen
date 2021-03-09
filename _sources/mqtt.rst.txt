Frischens Use of MQTT
=====================

The Frischen project uses MQTT to couple various functions together. This document aims to define how topics and values are used between programs.

Topic Structure
---------------

In MQTT, the topic specifies what function a message addresses. Topics are strings (encoded in UTF-8). A topic consists of one or more topic levels, separated by a slash. Topics are case-sensitive.

All topics start with the ``frischen`` prefix. Programs might use other topics for functions not related to the Frischen system, for example, to control the room lights in a signal tower.

The second level determines the operations area for the topics. This is typically the name of the signal tower from which this area is controlled.

The third level determines the class of equipment: either controls and indicators inside the signal tower, or track-side and other outside plant equipment, like turnouts, signals, etc. Inside controls and indicators have a topic level of ``panel``, track-side equipment uses ``trackside``.

The fourth level determines the type of element addressed, for example ``switch`` or ``turnout``.

The fifth level is the designation of the element, for example ``W3`` for turnout W3, or ``N3`` for the signal N3.

An optional sixth level allows distinguishing between commands from the signal tower to the element, and status reports from the element to the signal tower.

Examples
________

* ``frischen/etal/panel/turnout/W13``: position, locked state and occupied state of turnout W13 as determined by the signal tower and displayed on the operating panel.
* ``frischen/etal/panel/button/W13``: the button as part of the panel module. Pressing or releasing the button will send a message.
* ``frischen/etal/trackside/turnout/W13/command``: Commands from the signal tower to the turnout: change position.
* ``frischen/etal/trackside/turnout/W13/status``: Reports from the turnout to the signal tower: current position, end position reached. The turnout sends a status report every time the status changes.

