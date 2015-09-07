import common
from networking import TableConnectionCreator

with common.runtool(14) as parameters:
  table, fromIDField, toIDField, interFields, places, placesIDField, placesFields, network, cost, searchDist, speedupStr, speedupDist, location, outName = parameters
  interFieldList = common.parseFields(interFields)
  placesFieldList = common.parseFields(placesFields)
  link = TableConnectionCreator(table, [fromIDField, toIDField], places, placesIDField, location)
  link.addLinkFields(interFieldList)
  link.addPlaceFields(placesFieldList)
  if common.toBool(speedupStr, 'geometry speedup switch'):
    link.speedupOn(common.toFloat(speedupDist, 'maximum geometry speedup range'))
  link.loadNetwork(network, cost, searchDist)
  link.loadPlaces()
  link.output(outName)
  link.close()
