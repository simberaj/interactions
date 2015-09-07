import common, arcpy

with common.runtool(4) as parameters:
  zones, massFld, reg1Fld, reg2Fld = parameters
  equal = 0
  nonequal = 0
  zoneRows = arcpy.SearchCursor(zones)
  for row in zoneRows:
    if row.getValue(reg1Fld) == row.getValue(reg2Fld):
      equal += row.getValue(massFld)
    else:
      nonequal += row.getValue(massFld)
  del zoneRows
  equality = equal / float(equal + nonequal)
  common.message('Equality: %.5f %%' % (equality * 100))
