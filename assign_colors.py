import common, colors, loaders

with common.runtool(7) as parameters:
  zoneLayer, idFld, coreQuery, colorFld, colorFile, randomizeColors, neighTable = parameters
  shuffle = common.toBool(randomizeColors, 'color randomization switch')
  if not neighTable:
    common.progress('computing feature neighbourhood')
    import conversion
    neighTable = conversion.generateNeighbourTableFor(zoneLayer, idFld)
  common.progress('loading neighbourhood')
  neighbourhood = loaders.NeighbourTableReader(neighTable).read()
  common.debug(neighbourhood)
  common.progress('loading color setup')
  chooser = colors.ColorChooser(neighbourhood, colorFile)
  common.progress('assigning colors')
  colored = chooser.colorHeuristically(shuffle=shuffle)
  common.progress('writing output')
  loaders.ColorMarker(zoneLayer, inSlots={'id' : idFld}, outSlots={'color' : colorFld}, outCallers={'color' : 'getColor'}, where=coreQuery).mark(colored)
  # # TODO
  # common.progress('creating color field')
  # if colorFld not in common.fieldList(zoneLayer):
    # arcpy.AddField_management(zoneLayer, colorFld, 'TEXT')
  # zoneRows = arcpy.UpdateCursor(zoneLayer, coreQuery)
  # zoneColors = defaultdict(str)
  # for row in zoneRows:
    # id = row.getValue(idFld)
    # if id in colored:
      # row.setValue(colorFld, colored[id].getColor())
      # zoneRows.updateRow(row)
  # del zoneRows

