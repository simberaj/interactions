import arcpy, common
from networking import BulkInteractionCreator

PARAM_COUNT = 13

with common.runtool(PARAM_COUNT) as parameters:
  places, placesIDField, network, impedance, cutoff, cutoffFld, numToFind, numToFindFld, searchDist, chosenFields, excludeSelf, location, outputName = parameters
  transferFieldList = common.parseFields(chosenFields)
  conn = BulkInteractionCreator(places, placesIDField, location,
    excludeSelf=common.toBool(excludeSelf, 'self-interaction switch'))
  conn.loadNetwork(network, impedance, cutoff=cutoff, numToFind=numToFind, cutoffFld=cutoffFld, numToFindFld=numToFindFld, searchDist=searchDist)
  conn.addPlaceFields(transferFieldList)
  conn.loadPlaces()
  conn.solve()
  conn.output(outputName, PARAM_COUNT)
  conn.close()
