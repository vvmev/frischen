(function() {
  /**
   * Set up the E-Tal panel.
   */
  Promise.all([SpDrL20Panel.loadUri("../libs/spdrl20.svg"), SpDrL20Panel.contentLoaded])
    .then(results => {
      let panel = new SpDrL20Panel.Panel(6, 16, 66, 66, 'panel', new SpDrL20Panel.PanelClient('etal'))
      panel.createSymbolsFromSVG(results[0])

      // outer buttons
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

      // counters
      panel.pos(1, 8).tower().label("s", "Ef")
      panel.pos(1, 9).flipHV().counter("FHT")
      panel.pos(1, 10).flipHV().counter("ErsGT")
      panel.pos(1, 11).flipHV().counter("WHT")
      panel.pos(1, 12).flipHV().counter("AsT")

      // track 1
      panel.pos(2, 0).flipHV().triangle("blockstart-m").label("l", "n.Ma")
      panel.pos(2, 1).trackH("1-1")
      panel.pos(2, 2).trackH("1-1").button("p1p3").label("l", "p1/p3")
      panel.pos(2, 3).trackH("1-1")
      panel.pos(2, 4).flipV().turnout("W1").button("W1").label("s", "1")
      panel.pos(2, 5).flipHV().trackHt()
        .signalS("P1").signalA("P1").signalH("P1")
        .button("P1").label("l", "P1")
      panel.pos(2, 6).trackH("1-4")
      panel.pos(2, 7).trackH("1-4")
      panel.pos(2, 8).trackH("1-4").platform("1-4", "1")
      panel.pos(2, 9).trackH("1-4")
      panel.pos(2, 10).trackH("1-4")
      panel.pos(2, 11).trackH("1-4")
      panel.pos(2, 12).flipHV().turnout("W13").button("W13").label("s", "13")
      panel.pos(2, 13).flipHV()
        .signalD("p1p3").signalA("F").signalH("F")
        .button("F").label("l", "F")
      panel.pos(2, 14).trackH("1-6")
      // Streckentastensperre ausgelöst: Bezeichnungsfeld blinkt gelb
      panel.pos(2, 15).flipHV().trackHt()
        .signalD("f").triangle("blockend-d")
        .button("blockend-d").label("s", "v.Db")

      // track 2
      panel.pos(3, 0).trackHt()
        .signalD("a").triangle("blockend-m")
        .button("blockend-m").label("s", "v.Ma")
      panel.pos(3, 1).trackH("2-1")
      panel.pos(3, 2).trackHt()
        .signalD("n2n3").signalA("A").signalH("A")
        .button("A").label("l", "A")
      panel.pos(3, 3).trackH("2-2")
      panel.pos(3, 4).flipH().turnout("W2").button("W2").label("s", "2")
      panel.pos(3, 5).trackH("2-3")
      panel.pos(3, 6).flipV().turnout("W3").button("W3").label("s", "3")
      panel.pos(3, 7).trackH("2-4")
      panel.pos(3, 8).flipV().trackH("2-4").platform("2-4", "2")
      panel.pos(3, 9).trackHt()
        .signalS("N2").signalA("N2").signalH("N2")
        .button("N2").label("l", "N2")
      panel.pos(3, 10).flipHV().turnout("W11").button("W11").label("s", "11")
      panel.pos(3, 11).trackH("2-5")
      panel.pos(3, 12).turnout("W12").button("W12").label("s", "12")
      panel.pos(3, 13).trackH("2-6")
      panel.pos(3, 14).trackH("2-6").button("n2n3").label("l", "n2/n3")
      // Streckenwiederholungsperre Beschriftungsfeld: rot
      panel.pos(3, 15).triangle("blockstart-d").label("l", "n.Db")

      // track 3
      panel.pos(4, 5).trackHt()
      panel.pos(4, 6).flipH().turnout("W4").button("W4").label("s", "4")
      panel.pos(4, 7).flipHV().trackHt()
        .signalS("P3").signalA("P3").signalH("P3")
        .button("P3").label("l", "P3")
      panel.pos(4, 8).trackH("3-4").platform("3-4", "3")
      panel.pos(4, 9).trackHt()
        .signalS("N3").signalA("N3").signalH("N3")
        .button("N3").label("l", "N3")
      panel.pos(4, 10).turnout("W10").button("W10").label("s", "10")
      panel.pos(4, 11).trackHt()
    })

})();