import arcpy, common

with common.runtool(4) as parameters:
  common.progress('loading tool parameters')
  interLayer, fromFld, toFld, mergeFldsStr = parameters
  mergeFlds = mergeFldsStr.split(';')
  mergeRange = range(len(mergeFlds))
  # common.message('Found %i interactions.' % common.count(interLayer))
  inter = {}
  common.progress('loading interactions')
  readCursor = arcpy.SearchCursor(interLayer)
  for row in readCursor:
    fields = []
    source = row.getValue(fromFld)
    target = row.getValue(toFld)
    mergeVals = [row.getValue(fld) for fld in mergeFlds]
    inter[(source, target)] = mergeVals
    reversed = (target, source)
    # if reversed in inter:
      # inter[(source, target)] = inter[reversed]
      # inter[reversed] = mergeVals
    # else:
      # inter[(source, target)] = mergeVals
  del readCursor, row
  common.progress('creating output fields')
  outFlds = [('M_' + fld)[:10] for fld in mergeFlds]
  existFlds = common.fieldList(interLayer)
  for i in range(len(outFlds)):
    if outFlds[i] in existFlds:
      common.warning('Field %s already exists, contents will be overwritten' % outFlds[i])
      arcpy.DeleteField_management(interLayer, outFlds[i])
    else:
      arcpy.AddField_management(interLayer, outFlds[i], common.fieldType(type(mergeVals[i]))) # uses mergeVals from previous cycle... dragons
  common.progress('writing output')
  writeCursor = arcpy.UpdateCursor(interLayer)
  for row in writeCursor:
    reversed = (row.getValue(toFld), row.getValue(fromFld))
    if reversed in inter:
      values = inter[reversed]
      for i in range(len(values)):
        row.setValue(outFlds[i], values[i])
    else:
      for i in range(len(outFlds)):
        row.setNull(outFlds[i])
    writeCursor.updateRow(row)
  del writeCursor, row