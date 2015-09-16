import arcpy, common, randomize

with common.runtool(3) as parameters:
  conns, sdStr, target = parameters
  sd = common.toFloat(sdStr, 'standard deviation of position change')
  common.progress('copying connections')
  arcpy.CopyFeatures_management(conns, target)
  shpFld = arcpy.Describe(target).ShapeFieldName

  prog = common.progressor('randomizing', common.count(target))
  rows = arcpy.UpdateCursor(target)
  for row in rows:
    newPt = randomize.randomizeConnection(row.getValue(shpFld), sd)
    row.setValue(shpFld, newPt)
    rows.updateRow(row)
    prog.move()

  prog.end()
  del row, rows
