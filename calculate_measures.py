import common, regionalization

with common.runtool(regionalization.getMainParamCount()) as parameters:
  regionalization.runByParams(*parameters, delimit=False)
  
  # zoneLayer, zoneIDFld, zoneMassFld, zoneCoopFld, zoneColFld, \
    # interLayer, interStrengthFld, interFromIDFld, interToIDFld, \
    # regionFld, exclavePenal, neighTable, colorFld, measureFlds = common.parameters(14)
  # exclavePenal = common.toFloat(exclavePenal, 'exclave penalization percentage') if exclavePenal else None
  # measureFldList = common.parseFields(measureFlds)
  # regload = loaders.RegionalLoader()
  # regload.requireZones(zoneLayer, zoneIDFld, zoneMassFld, zoneColFld)
  # if regionFld:
    # regload.requirePresets(regionFld, zoneCoopFld, regionalization.Regionalizer(objects.FunctionalRegion))
  # regload.requireInteractions(interLayer, interFromIDFld, interToIDFld, interStrengthFld)
  # regload.requireNeighbourhood(neighTable)
  # regload.load()
  
  # TODO
  # if zoneColFld and colorFld:
    # common.progress('calculating assignment colors')
    # for zone in reg.getZones(): zone.calcFuzzyColor('hamplMembership')
  # common.progress('writing output')
  # zoneLoader.output(zones, None, colorFld=colorFld, measures=measureFldList)
