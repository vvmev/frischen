var SpDrL20Panel = (function() {

  // stolen from https://github.com/jonathantneal/document-promises
  const thenify = (type, readyState) => new Promise(resolve => {
  	const listener = () => {
  		if (readyState.test(document.readyState)) {
  			document.removeEventListener(type, listener);
  			resolve();
  		}
  	};
  	document.addEventListener(type, listener);
  	listener();
  });
  const contentLoaded = thenify('DOMContentLoaded', /^(?:interactive|complete)$/);

  let stringToBoolean = function(string) {
      switch(string.toLowerCase().trim()){
          case "t": case "true": case "yes": case "1": return true;
          case "f": case "false": case "no": case "0": case null: return false;
          default: return Boolean(string);
      }
  }

  let stringToBooleanArray = function(string) {
    return string.split(",").map(stringToBoolean)
  }

  /**
   * Returns a promise to load a document asynchronously.
   */
  let loadUri = function(uri, f) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open("GET", uri)
      xhr.onload = () => resolve(xhr.response)
      xhr.onerror = () => reject(xhr.statusText)
      xhr.send()
    })
  }


  /**
   * MQTT client
   */
  let PanelClient = class {
    constructor(name) {
      this.client = new Paho.MQTT.Client(location.hostname, Number(location.port),
        `frischen-${name}`);
      this.topic = `frischen/${name}/panel`;
      this.subscriptions = {}
      this.is_connected = false

      this.client.onConnectionLost = resp => this.onConnectionLost(resp)
      this.client.onMessageArrived = msg => this.onMessageArrived(msg)
      this.client.connect({onSuccess: options => this.onConnected(options)})
    }

    onConnected(options) {
      try {
        let topic = this.topic
        for(let k of Object.keys(this.subscriptions)) {
          this.client.subscribe(k);
        }
        this.is_connected = true
      } catch(e) {
        console.log(`onConnected: ${e}`)
      }
    }

    onConnectionLost(resp) {
      try {
        console.log(`Connection lost, reconnecting`)
        if (resp.errorCode !== 0) {
          this.is_connected = false
          this.client.connect({onSuccess: this.onConnected})
        }
      } catch(e) {
        console.log(`onConnectionLost: ${e}`)
      }
    }

    onMessageArrived(msg) {
      try {
        let k = msg.destinationName
        if (this.subscriptions[k] !== undefined) {
          for (let callback of this.subscriptions[k]) {
            callback(k, msg.payloadString)
          }
        } else {
          console.log(`unexpected message ${msg.destinationName} = ${msg.payloadString} received`)
        }
      } catch(e) {
        console.log(`onMessageArrived: ${e}`)
      }
    }

    send(kind, subject, value) {
      let message = new Paho.MQTT.Message(value);
      message.destinationName = `${this.topic}/${kind}/${subject}`;
      this.client.send(message);
    }

    subscribe(kind, subject, callback) {
      this.subscribeGeneral(`${this.topic}/${kind}/${subject}`, callback)
    }

    subscribeGeneral(k, callback) {
      if (this.subscriptions[k] === undefined) {
        this.subscriptions[k] = new Array()
      }
      this.subscriptions[k].push(callback)
      if (this.is_connected) {
        for (let c of this.subscriptions[k]) {
          this.client.subscribe(k)
        }
      }
    }
  }


  let Blinker = class {
    constructor(elements, cssClass) {
      if (Array.isArray(elements))
        this.elements = elements
      else
        this.elements = [elements]
      this.cssClass = cssClass
    }

    change(v) {
      if (stringToBoolean(v)) {
        for (let e of this.elements) {
          e.addClass(this.cssClass)
        }
      } else {
        for (let e of this.elements) {
          e.removeClass(this.cssClass)
        }
      }
    }

    stop() {
      for (let e of this.elements) {
        e.removeClass(this.cssClass)
      }
    }
  }


  let PanelButtonManager = class {
    constructor() {
      this.buttons = []
      this.timer = undefined
      this.timeout = 5000
    }
    add(button) {
      this.buttons.push(button)
    }
    mousedown() {
      if (this.timer !== undefined) {
        clearTimeout(this.timer)
      }
      this.timer = setTimeout(() => {
        for (button of this.buttons) {
          if (button.locked) {
            button.pressed = false
            button.locked = false
            button.updateCallback(button.pressed)
          }
        }
        this.timer = undefined
      }, this.timeout)
    }
  }

  let panel_button_manager = new PanelButtonManager()

  /**
   * A combination momentary and regular switch. Pressing the mouse on the
   * element will engange the switch. A double click will lock it in the on
   * position, and pressing the mouse again will release it once the mouse
   * button is lifted.
   */
  let PanelButton = class {
    constructor(element, updateCallback) {
      this.pressed = false
      this.locked = false
      this.updateCallback = updateCallback
      this.timer = undefined
      panel_button_manager.add(this)
      element.on('mousedown', event => {
        if (!this.pressed) {
          this.pressed = true
          this.updateCallback(this.pressed)
        }
        panel_button_manager.mousedown()
        event.stopPropagation()
        event.preventDefault()
      })
      element.on('mouseup', event => {
        if (this.locked) {
          this.pressed = false
          this.locked = false
          this.updateCallback(this.pressed)
        } else {
          if (this.timer === undefined) {
            this.timer = setTimeout(() => {
              this.pressed = false
              this.timer = undefined
              this.updateCallback(this.pressed)
            }, 250)
          } else {
            clearTimeout(this.timer)
            this.timer = undefined
            this.locked = true
          }
        }
        event.stopPropagation()
        event.preventDefault()
      })
      element.on('click', e => {
        e.stopPropagation()
        e.preventDefault()
      })
      element.on('dblclick', e => {
        e.stopPropagation()
        e.preventDefault()
      })
    }
  }


  /**
   * One module position on the panel
   */
  let PanelPos = class {
    constructor(panel, row, col) {
      this.panel = panel
      this.row = row
      this.col = col
      this.module = panel.panelmodules.group().id(`frischen-pos-${row}-${col}`)
      this.module.move(col*panel.moduleWidth, row*panel.moduleHeight)
      this.background = this.module.group().id(`frischen-bg-${row}-${col}`)
      let r = this.background.rect(panel.moduleWidth, panel.moduleHeight)
      r.addClass("frischen-module-box")
      r.addClass("frischen-module-box-border")
      this.inside = this.module.group().id(`frischen-inside-${row}-${col}`)
      this.tracks = this.inside.group().addClass('frischen-track')
      this.indicators = this.inside.group().addClass('frischen-indicator')
      this.labels = this.inside.group().addClass('frischen-label')
      this.buttons = this.inside.group().addClass('frischen-button')
      this.labeltext = this.module.group()
      this.clicktarget = this.module.group()
      this.blinker = undefined
    }

    addClasses(elements, cs) {
      for (let e of elements) {
        for (let c of cs) {
          e.addClass(c)
        }
      }
    }

    removeClasses(elements, cs) {
      for (let e of elements) {
        for (let c of cs) {
          e.removeClass(c)
        }
      }
    }

    subscribeTrack(indicator, elements) {
      this.panel.client.subscribe('track', indicator, (k, v) => {
        [this.occupied, this.locked] = stringToBooleanArray(v)
        this.removeClasses(elements, ['frischen-track-locked', 'frischen-track-occupied'])
        if (this.occupied)
            this.addClasses(elements, ['frischen-track-occupied'])
        else if (this.locked)
            this.addClasses(elements, ['frischen-track-locked'])
      })
    }

    /**
     * Helper method to add a symbol to a group
     */
    symbol(where, symbol) {
      return where.put(this.panel.symbols[symbol].clone())
    }

    blockend(indicator, label) {
      this.symbol(this.tracks, 'frischen-block-arrow')
      let triangle = this.symbol(this.indicators, 'frischen-block-arrow-indicator')
        .addClass('frischen-signal-red')
      let n = indicator.split("-")[0]
      this.panel.client.subscribe(n, indicator, (k, v) => {
        [this.occupied, this.blocked, this.clearance_lock] = stringToBooleanArray(v)
        if (this.blocked) {
          triangle.addClass('frischen-signal-red')
          triangle.removeClass('frischen-signal-white')
        } else {
          triangle.removeClass('frischen-signal-red')
          triangle.addClass('frischen-signal-white')
        }
        if (this.blinker !== undefined) {
          this.panel.removeBlinker(this.blinker)
          this.blinker = undefined
        }
        if (!this.clearance_lock) {
          this.blinker = this.panel.addBlinker([this.labels], 'frischen-switch-position')
        }
        console.log('blocked: ' + this.blocked + ', clearance: ' + this.clearance_lock)
      })
      this.label("s", label)
      return this
    }

    button(actuator) {
      let button = this.symbol(this.buttons, 'frischen-button')
      let state = '0'
      let b = this.clicktarget.rect(this.panel.moduleWidth, this.panel.moduleHeight)
      b.addClass('frischen-clicktarget')
      let pb = new PanelButton(b, v => {
        state = v ? '1' : '0'
        if (v) {
          button.addClass('frischen-button-pressed')
        } else {
          button.removeClass('frischen-button-pressed')
        }
        this.panel.client.send('button', actuator, state)
      })
      return this
    }

    counter(name) {
      let label = this.panel.symbols['frischen-counter'].clone()
      let value = "0000"
      this.inside.put(label)
      let pos = label.rbox(this.module)
      let text = this.module.plain(value)
      text.attr('font-family', null)
      text.attr('style', null)
      text.addClass('frischen-counter')
      text.move(pos.cx, pos.cy-8) // looks OK for 14px font size
      this.panel.client.subscribe('counter', name, function(k, v) {
        text.node.innerHTML = ('0'.repeat(4 - v.length) + v)
      })
      return this
    }

    flipH() {
      this.inside.flip('x', .5*this.panel.moduleWidth)
      return this
    }

    flipV() {
      this.inside.flip('y', .5*this.panel.moduleHeight)
      return this
    }

    flipHV() {
      this.inside.flip(.5*this.panel.moduleHeight)
      return this
    }

    label(size, name) {
      this.label = this.panel.symbols['frischen-label-' + size].clone()
      this.labels.put(this.label)
      let pos = this.label.rbox(this.module)
      let text = this.labeltext.plain(name)
      text.addClass('frischen-label')
      text.attr('font-family', null)
      text.attr('style', null)
      text.addClass('frischen-label-' + size)
      text.move(pos.cx, pos.cy-8) // looks OK for 14px font size
      return this
    }

    platform(indicator, name) {
      this.symbol(this.tracks, 'frischen-platform')
      this.label("c", name)
      this.subscribeTrack(indicator, [this.label])
      return this
    }

    turnout(indicator) {
      this.occupied = false
      this.position = false
      this.moving = false
      this.locked = false
      this.blocked = false
      this.symbol(this.tracks, 'frischen-track-h')
      this.symbol(this.tracks, 'frischen-track-d')
      let leg1 = this.symbol(this.indicators, 'frischen-track-indicator-d1')
      let leg2 = this.symbol(this.indicators, 'frischen-track-indicator-h1')
      leg2.addClass('frischen-switch-position')
      // also: blinks red if trailing point movement throws switch
      let track1 = this.symbol(this.indicators, 'frischen-track-indicator-d2')
      let track2 = this.symbol(this.indicators, 'frischen-track-indicator-h2')
      let occupied = [track1, track2]
      this.panel.client.subscribe('turnout', indicator, (k, v) => {
        [this.occupied, this.position, this.moving, this.locked, this.blocked] = stringToBooleanArray(v)
        console.log("turnout " + k + " position " + this.position + ", moving " + this.moving)
        if (!this.moving && this.blinker !== undefined) {
          this.panel.removeBlinker(this.blinker)
          this.blinker = undefined
        }
        if (this.position) {
          this.active = leg1.addClass('frischen-switch-position')
          leg2.removeClass('frischen-switch-position')
        } else {
          leg1.removeClass('frischen-switch-position')
          this.active = leg2.addClass('frischen-switch-position')
        }
        if (this.moving) {
          this.blinker = this.panel.addBlinker([this.active], 'frischen-switch-position')
        }
        let active = this.position ? track1 : track2
        this.removeClasses([track1, track2], ['frischen-track-locked'])
        if (this.locked) {
          this.addClasses([active], ['frischen-track-locked'])
        }
        if (this.occupied) {
          this.removeClasses([track1, track2], ['frischen-track-locked'])
          this.addClasses(occupied, ['frischen-track-occupied'])
        } else {
          this.removeClasses(occupied, ['frischen-track-occupied'])
        }
      })
      return this
    }

    signalA(indicator) {
      this.symbol(this.tracks, 'frischen-alt-signal')
      let light = this.symbol(this.indicators, 'frischen-alt-signal-indicator')
      this.panel.client.subscribe('signal', indicator, (k, v) => {
        switch(v) {
          case 'Hp0-Zs1':
          case 'Zs1':
            light.addClass('frischen-signal-white')
            break
          default:
            light.attr('class', '');
            break
        }
      })
      return this
    }

    signalD(indicator) {
      this.symbol(this.tracks, 'frischen-distant-signal')
      let light = this.symbol(this.indicators, 'frischen-distant-signal-indicator')
      this.panel.client.subscribe('signal', indicator, function(k, v) {
        light.attr('class', '');
        switch(v) {
          case 'Vr0':
            light.attr('class', 'frischen-signal-yellow'); break
          case 'Vr1':
          case 'Vr2':
            light.attr('class', 'frischen-signal-green'); break
        }
      })
      return this
    }

    signalH(indicator) {
      this.symbol(this.tracks, 'frischen-starting-signal')
      let light = this.symbol(this.indicators, 'frischen-starting-signal-indicator').addClass('frischen-signal-red')
      this.panel.client.subscribe('signal', indicator, function(k, v) {
        switch(v) {
          case 'Hp1':
          case 'Hp2':
            light.attr('class', 'frischen-signal-green'); break
          default:
            light.attr('class', 'frischen-signal-red'); break
        }
      })
      return this
    }

    signalS(indicator) {
      this.symbol(this.tracks, 'frischen-shunting-signal')
      let light = this.symbol(this.indicators, 'frischen-shunting-signal-indicator')
      this.panel.client.subscribe('signal', indicator, function(k, v) {
        switch(v) {
          case 'Hp0-Sh1':
          case 'Sh1':
          case 'Ra12':
            light.attr('class', 'frischen-signal-white'); break
          default:
            light.attr('class', ''); break
        }
      })
      return this
    }

    tower() {
      this.symbol(this.tracks, 'frischen-tower')
      return this
    }

    trackD(indicator) {
      this.symbol(this.tracks, 'frischen-track-d')
      let occupied = this.symbol(this.indicators, 'frischen-track-indicator-d')
      this.subscribeTrack(indicator, [occupied])
      return this
    }

    trackH(indicator) {
      this.symbol(this.tracks, 'frischen-track-h')
      let occupied = this.symbol(this.indicators, 'frischen-track-indicator-h')
      this.subscribeTrack(indicator, [occupied])
      return this
    }

    trackHt() {
      this.symbol(this.tracks, 'frischen-track-h')
      return this
    }

    trackV(indicator) {
      this.symbol(this.tracks, 'frischen-track-v')
      let occupied = this.symbol(this.indicators, 'frischen-track-indicator-v')
      this.subscribeTrack(indicator, [occupied])
      return this
    }

    triangle(indicator) {
      this.symbol(this.tracks, 'frischen-block-arrow')
      let triangle = this.symbol(this.indicators, 'frischen-block-arrow-indicator')
        .addClass('frischen-signal-red')
      let n = indicator.split("-")[0]
      this.panel.client.subscribe(n, indicator, (k, v) => {
        [this.occupied, this.blocked, this.clearance_lock] = stringToBooleanArray(v)
        if (this.blocked) {
          triangle.addClass('frischen-signal-red')
          triangle.removeClass('frischen-signal-white')
        } else {
          triangle.removeClass('frischen-signal-red')
          triangle.addClass('frischen-signal-white')
        }
        console.log('blocked: ' + this.blocked)
      })
      return this
    }
  }

  /**
   * The panel, with frame, symbols and various helpers.
   */
  let Panel = class {
    constructor(rows, cols, moduleHeight, moduleWidth, id, client) {
      this.rows = rows
      this.cols = cols
      this.moduleHeight = moduleHeight
      this.moduleWidth = moduleWidth
      this.id = this.id
      this.border = moduleWidth/3
      this.modules = new Array(rows)
      this.paneldrawing = null
      this.symbols = {}
      this.client = client
      this.blinking = []
      let blinking = this.blinking
      this.client.subscribeGeneral('frischen/time/1hz', function(k, v) {
        for (let b of blinking) {
          b.change(v)
        }
      })

      this.paneldrawing = SVG(id)
      this.paneldrawing.size(this.moduleWidth*this.cols + 2*this.border,
        this.moduleHeight*this.rows + 2*this.border)
      let panelFrameGradient = this.paneldrawing.gradient('linear', (stop) => {
        stop.from()
        stop.at(0, "#eee")
        stop.at(0.2, "#888")
        stop.at(0.5, "#eee")
        stop.at(0.6, "#888")
        stop.at(1, "#eee")
      }).attr("gradientTransform", "rotate(27)")
      this.paneldrawing.rect(this.paneldrawing.width(),
        this.paneldrawing.height()).fill(panelFrameGradient)
      this.paneldrawing.gradient('linear', (stop) => {
        stop.from()
        stop.at(0, "#222")
        stop.at(0.5, "#777")
        stop.at(1, "#222")
      }).attr("gradientTransform", "rotate(90)").id('countergradient')
      this.panelmodules = this.paneldrawing.group()
      this.panelmodules.move(this.border, this.border)

      for (let row=0; row<this.rows; row++) {
        this.modules[row] = Array(cols)
        for (let col=0; col<this.cols; col++) {
          this.modules[row][col] = new PanelPos(this, row, col)
        }
      }
    }

    createSymbolsFromSVG(svg) {
      let symbolsdef = this.paneldrawing.defs().group().id('frischen-symbols')
      symbolsdef.svg(svg)
      symbolsdef = symbolsdef.select("svg").first()
      let viewBox = symbolsdef.attr("viewBox").split(" ")
      let scale = this.moduleWidth / viewBox[2]

      let symbols = this.symbols
      let paneldefs = this.paneldrawing.defs()
      let layers = symbolsdef.select('g[inkscape\\:groupmode="layer"]')
      layers.each(function(i, children) {
        let label = this.attr('inkscape:label')
        if (label.startsWith('frischen-')) {
          this.attr('style', null)
          this.each(function(i, e) {
            this.attr('style', null)
          }, true)
          let symbol = paneldefs.group()
          symbol.id(label)
          symbol.addClass(label)
          symbol.transform({scale: scale, cx: 0, cy: 0})
          symbol.put(this.clone())
          symbols[label] = symbol
        }
      })
    }

    pos(row, col) {
      if (!this.modules[row][col])
        this.modules[row][col] = new this.PanelPos(row, col)
      return this.modules[row][col]
    }

    addBlinker(elements, cssClass) {
      let blinker = new Blinker(elements, cssClass)
      this.blinking.push(blinker)
      return blinker
    }

    removeBlinker(blinker) {
      let i = this.blinking.indexOf(blinker)
      if (i !== -1) {
        this.blinking[i].stop()
        this.blinking.splice(i, 1)
      }
    }
  }

  return {
    'contentLoaded': contentLoaded,
    'loadUri': loadUri,
    'Panel': Panel,
    'PanelClient': PanelClient,
  }
})();
