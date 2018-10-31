(function() {

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

  let stringToBoolean = function(string){
      switch(string.toLowerCase().trim()){
          case "true": case "yes": case "1": return true;
          case "false": case "no": case "0": case null: return false;
          default: return Boolean(string);
      }
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
      this.client = new Paho.MQTT.Client(location.hostname, Number(location.port), `frischen-${name}`);
      this.topic = `frischen/${name}`;
      this.subscriptions = {}
      this.is_connected = false

      this.subscriptions['frischen/time/1hz'] = m => {
        console.log("1hz")
      }

      //this.client.onConnectionLost = resp => this.onConnectionLost(resp)
      this.client.onMessageArrived = msg => this.onMessageArrived(msg)
      this.client.connect({onSuccess: options => this.onConnected(options)})
    }

    onConnected(options) {
      try {
        let topic = this.topic
        console.log(`Connected, making ${Object.keys(this.subscriptions).length} subscriptions`)
        for(let k of Object.keys(this.subscriptions)) {
          this.client.subscribe(`${topic}/${k}`);
          console.log(`subscribing to ${k} (onConnected)`)
        }
        this.is_connected = true
      } catch(e) {
        console.log(`onConnected: ${e}`)
      }
    }

    onConnectionLost(resp) {
      try {
        console.log(`Connection lost`)
        if (resp.errorCode !== 0) {
          this.is_connected = false
          //this.client.connect({onSuccess: this.onConnected})
        }
      } catch(e) {
        console.log(`onConnectionLost: ${e}`)
      }
    }

    onMessageArrived(msg) {
      try {
        if (msg.destinationName.indexOf(this.topic) == 0) {
          let k = msg.destinationName.slice(this.topic.length + 1);
          // s = stringToBoolean(msg.payloadString);
          console.log(`message ${k} = ${msg.payloadString} received`)
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
      let k = `${kind}/${subject}`
      if (this.subscriptions[k] === undefined) {
        this.subscriptions[k] = new Array()
      }
      this.subscriptions[k].push(callback)
      if (this.is_connected) {
        console.log(`subscribing to ${k}`)
        for (let c of this.subscriptions[k]) {
          this.client.subscribe(`${this.topic}/${k}`)
        }
      }
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
    }

    subscribeTrack(indicator, elements) {
      this.panel.client.subscribe('track', indicator, function(k, v) {
        if (stringToBoolean(v)) {
          for (let e of elements) {
            e.addClass('frischen-track-occupied')
          }
        } else {
          for (let e of elements) {
            e.removeClass('frischen-track-occupied')
          }
        }
      })
    }

    /**
     * Helper method to add a symbol to a group
     */
    symbol(where, symbol) {
      return where.put(this.panel.symbols[symbol].clone())
    }

    button(actuator) {
      let button = this.symbol(this.buttons, 'frischen-button')
      let state = '0'
      let b = this.buttons.rect(this.panel.moduleWidth, this.panel.moduleHeight)
      b.addClass('frischen-clicktarget')
      b.on('click', e => {
        console.log(`button ${actuator}`)
        state = state == '0' ? '1' : '0'
        this.panel.client.send('button', actuator, state)
      })
      this.panel.client.subscribe('button', actuator, function(k, v) {
        state = v
        if (stringToBoolean(v)) {
          button.addClass('frischen-button-pressed')
        } else {
          button.removeClass('frischen-button-pressed')
        }
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
      let label = this.panel.symbols['frischen-label-' + size].clone()
      this.labels.put(label)
      let pos = label.rbox(this.module)
      let text = this.module.plain(name)
      text.addClass('frischen-label')
      text.attr('font-family', null)
      text.attr('style', null)
      text.addClass('frischen-label-' + size)
      text.move(pos.cx, pos.cy-8) // looks OK for 14px font size
      return this
    }

    platform(name) {
      this.symbol(this.tracks, 'frischen-platform')
      this.label("c", name)
      return this
    }

    switch(indicator) {
      this.symbol(this.tracks, 'frischen-track-h')
      this.symbol(this.tracks, 'frischen-track-d')
      let leg1 = this.symbol(this.indicators, 'frischen-track-indicator-d1')
      let leg2 = this.symbol(this.indicators, 'frischen-track-indicator-h1')
      leg2.addClass('frischen-switch-position')
      let occupied1 = this.symbol(this.indicators, 'frischen-track-indicator-d2')
      let occupied2 = this.symbol(this.indicators, 'frischen-track-indicator-h2')
      this.panel.client.subscribe('switch', indicator, function(k, v) {
        if (stringToBoolean(v)) {
          leg1.addClass('frischen-switch-position')
          leg2.removeClass('frischen-switch-position')
        } else {
          leg1.removeClass('frischen-switch-position')
          leg2.addClass('frischen-switch-position')
        }
      })
      this.subscribeTrack(indicator, [occupied1, occupied2])
      return this
    }

    signalA(indicator) {
      this.symbol(this.tracks, 'frischen-alt-signal')
      let light = this.symbol(this.indicators, 'frischen-alt-signal-indicator')
      this.panel.client.subscribe('signal', indicator, function(k, v) {
        switch(v) {
          case 'Zs1':
            light.attr('class', 'frischen-signal-white'); break
          default:
            light.attr('class', ''); break
        }
      })
      return this
    }

    signalD(indicator) {
      this.symbol(this.tracks, 'frischen-distant-signal')
      let light = this.symbol(this.indicators, 'frischen-distant-signal-indicator')
      this.panel.client.subscribe('signal', indicator, function(k, v) {
        switch(v) {
          case 'Vr0':
            light.attr('class', 'frischen-signal-yellow'); break
          case 'Vr1':
          case 'Vr2':
            light.attr('class', 'frischen-signal-green'); break
          default:
            light.attr('class', ''); break
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
      let occupied = this.symbol(this.indicators, 'frischen-block-arrow-indicator')
      this.subscribeTrack(indicator, [occupied])
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
  }

  /**
   * Set up the E-Tal panel.
   */
  let init = function(svg) {
    let panel = new Panel(6, 16, 66, 66, 'panel', new PanelClient('etal'))
    panel.createSymbolsFromSVG(svg)

    panel.pos(0, 3).flipHV().button("WGT").label("l", "WGT")
    panel.pos(0, 4).flipHV().button("HaGT").label("l", "HaGT")
    panel.pos(0, 5).flipHV().button("SGT").label("l", "SGT")
    panel.pos(0, 7).flipHV().counter("Af").label("s", "Af")
    panel.pos(0, 9).flipHV().button("FHT").label("l", "FHT")
    panel.pos(0, 10).flipHV().button("ErsGT").label("l", "ErsGT")
    panel.pos(0, 11).flipHV().button("WHT").label("l", "WHT")
    panel.pos(0, 12).flipHV().button("AsT").label("l", "AsT")
    panel.pos(0, 13).flipHV().button("AsLT").label("l", "AsLT")
    panel.pos(0, 14).flipHV().button("BlGT").label("l", "BlGT")

    panel.pos(1, 8).tower().label("s", "Ef")
    panel.pos(1, 9).flipHV().counter("FHT")
    panel.pos(1, 10).flipHV().counter("ErsGT")
    panel.pos(1, 11).flipHV().counter("WHT")
    panel.pos(1, 12).flipHV().counter("AsT")

    panel.pos(2, 0).flipHV().triangle("199").label("l", "n.Ma")
    panel.pos(2, 1).trackH("198")
    panel.pos(2, 2).trackH("198").button("p1p3").label("l", "p1/p3")
    panel.pos(2, 3).trackH("198")
    panel.pos(2, 4).flipV().switch("W1").button("W1").label("s", "1")
    panel.pos(2, 5).flipHV().trackHt()
      .signalS("101").signalA("altP1").signalH("P1")
      .button("P1").label("l", "P1")
    panel.pos(2, 6).trackH("1")
    panel.pos(2, 7).trackH("1")
    panel.pos(2, 8).trackH("1").platform("1")
    panel.pos(2, 9).trackH("1")
    panel.pos(2, 10).trackH("1")
    panel.pos(2, 11).trackH("1")
    panel.pos(2, 12).flipHV().switch("W13").button("W13").label("s", "13")
    panel.pos(2, 13).trackH("102")
    panel.pos(2, 14).flipHV()
      .signalD("p1p3").signalA("altF").signalH("F")
      .button("F").label("l", "F")
      panel.pos(2, 15).flipHV().trackHt()
        .signalD("f").triangle("100")
        .button("block-end-d").label("s", "v.Db")

    panel.pos(3, 0).trackHt()
      .signalD("a").triangle("299")
      .button("block-end-m").label("s", "v.Ma")
    panel.pos(3, 1).trackH("298")
    panel.pos(3, 2).trackHt()
      .signalD("n2n3").signalA("altA").signalH("A")
      .button("A").label("l", "A")
    panel.pos(3, 3).trackH("297")
    panel.pos(3, 4).flipH().switch("W2").button("W2").label("s", "2")
    panel.pos(3, 5).trackH("296")
    panel.pos(3, 6).flipV().switch("W3").button("W3").label("s", "3")
    panel.pos(3, 7).trackH("2")
    panel.pos(3, 8).flipV().trackH("2").platform("2")
    panel.pos(3, 9).trackHt()
      .signalS("201").signalA("altN2").signalH("N2")
      .button("N2").label("l", "N2")
    panel.pos(3, 10).flipHV().switch("W11").button("W11").label("s", "11")
    panel.pos(3, 11).trackH("202")
    panel.pos(3, 12).switch("W12").button("W12").label("s", "12")
    panel.pos(3, 13).trackH("201")
    panel.pos(3, 14).trackH("201").button("n2n3").label("l", "n2/n3")
    panel.pos(3, 15).triangle("200").label("l", "n.Db")

    panel.pos(4, 4).flipHV().trackD("4.90")
    panel.pos(4, 5).trackH("4.90")
    panel.pos(4, 6).flipH().switch("W4").button("W4").label("s", "4")
    panel.pos(4, 7).flipHV().trackHt()
      .signalS("103").signalA("altP3").signalH("P3")
      .button("P3").label("l", "P3")
    panel.pos(4, 8).trackH("3").platform("3")
    panel.pos(4, 9).trackHt()
      .signalS("203").signalA("altN3").signalH("N3")
      .button("N3").label("l", "N3")
    panel.pos(4, 10).switch("W10").button("W10").label("s", "10")
    panel.pos(4, 11).trackHt()

    panel.pos(5, 4).trackV("4.90")
  }

  Promise.all([loadUri("l20-module.svg"), contentLoaded])
    .then(results => init(results[0]))
})();
