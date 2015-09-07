import common
from networking import ODJoiner

with common.runtool(6) as parameters:
  table, fromIDField, toIDField, places, placesIDField, placesFields = parameters
  placesFieldList = common.parseFields(placesFields)
  link = ODJoiner(table, [fromIDField, toIDField], places, placesIDField)
  link.addPlaceFields(placesFieldList)
  link.loadPlaces()
  link.join()
  link.close()  
