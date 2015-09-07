import arcpy, common
from networking import BulkConnectionCreator

PARAM_COUNT = 13

with common.runtool(PARAM_COUNT) as parameters:
  places, placesIDField, network, impedance, cutoff, cutoffFld, numToFind, numToFindFld, searchDist, chosenFields, excludeSelf, location, outputName = parameters
  transferFieldList = common.parseFields(chosenFields)
  conn = BulkConnectionCreator(places, placesIDField, location, 
    excludeSelf=common.toBool(excludeSelf, 'self-connection switch'))
  conn.loadNetwork(network, impedance, cutoff=cutoff, numToFind=numToFind, cutoffFld=cutoffFld, numToFindFld=numToFindFld, searchDist=searchDist)
  conn.addPlaceFields(transferFieldList)
  conn.loadPlaces()
  conn.solve()
  conn.output(outputName, PARAM_COUNT)
  conn.close()
