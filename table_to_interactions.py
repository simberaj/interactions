import common
from networking import TableInteractionCreator

with common.runtool(9) as parameters:
  table, fromIDField, toIDField, interFields, places, placesIDField, placesFields, location, outName = parameters
  interFieldList = common.parseFields(interFields)
  placesFieldList = common.parseFields(placesFields)
  link = TableInteractionCreator(table, [fromIDField, toIDField], places, placesIDField, location)
  link.addLinkFields(interFieldList)
  link.addPlaceFields(placesFieldList)
  link.loadPlaces()
  link.output(outName)
  link.close()
