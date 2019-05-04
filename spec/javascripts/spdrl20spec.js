describe('SpDrL20 signal tower',  function() {
  describe('exported symbols are defined', function() {
    it('Module is defined', function() {
      expect(SpDrL20Panel).toBeDefined()
    })
    it('contentLoaded is defined', function() {
      expect(SpDrL20Panel.contentLoaded).toBeDefined()
    })
    it('loadUri is defined', function() {
      expect(SpDrL20Panel.loadUri).toBeDefined()
    })
    it('Panel is defined', function() {
      expect(SpDrL20Panel.Panel).toBeDefined()
    })
    it('PanelClient is defined', function() {
      expect(SpDrL20Panel.PanelClient).toBeDefined()
    })
  })
  describe('Panel', function() {
    let svg
    beforeAll(function() {
      p = SpDrL20Panel.loadUri("../libs/spdrl20.svg")
      svg = await p
    })
    it('svg loaded', function() {
      expect(svg).toBeDefined()
    })
  })
})
