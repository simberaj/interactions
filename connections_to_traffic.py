import os, arcpy, common, loaders

DUPL_FILE = 'tmp_dupl'
MERGE_FILE = 'tmp_merged'
INTER_FILE = 'tmp_intersect'
SHPLEN_FLD = 'TMP_SHLEN'

class Halver(loaders.FunctionUpdater):
  requiredInputSlots = ['doubled']
  requiredOutputSlots = ['halved']
  
  @staticmethod
  def translate(inprow={'doubled' : 0.0}):
    return {'halved' : inprow['doubled'] / 2.0}

with common.runtool(4) as parameters:
  conns, trafFld, tolerance, outPath = parameters
  location = os.path.dirname(outPath)
  duplPath = common.addExt(os.path.join(location, DUPL_FILE))
  mergePath = common.addExt(os.path.join(location, MERGE_FILE))
  interPath = common.addExt(os.path.join(location, INTER_FILE))
  common.progress('preparing connections')
  arcpy.CopyFeatures_management(conns, duplPath)
  arcpy.Merge_management([conns, duplPath], mergePath)
  common.progress('intersecting connections')
  arcpy.Intersect_analysis([mergePath], interPath, 'ALL', tolerance, 'INPUT')
  # create a shape length field
  common.progress('marking traffic')
  arcpy.AddField_management(interPath, SHPLEN_FLD, 'Double')
  arcpy.CalculateField_management(interPath, SHPLEN_FLD, '!shape.length!', 'PYTHON_9.3')
  common.progress('summarizing traffic')
  arcpy.Dissolve_management(interPath, outPath, [SHPLEN_FLD], [[trafFld, 'SUM']], 'SINGLE_PART')
  common.progress('initializing traffic fields')
  arcpy.AddField_management(outPath, trafFld, common.typeOfField(conns, trafFld))
  sumFld = 'SUM_' + trafFld # TODO: shapefile field name length adjustments...
  Halver(outPath, {'doubled' : sumFld}, {'halved' : trafFld}).decompose('computing traffic fields')
  # prog = common.progressor('adjusting total flow counts', common.count(outPath))
  
  # outRows = arcpy.UpdateCursor(outPath)
  # for row in outRows:
    # unduplVal = row.getValue(sumFld) / 2
    # row.setValue(trafFld, unduplVal)
    # outRows.updateRow(row)
    # prog.move()
  # del row, outRows
  # prog.end()
  common.progress('deleting temporary fields')
  arcpy.DeleteField_management(outPath, [sumFld, SHPLEN_FLD])
  common.progress('deleting temporary files')
  common.delete(duplPath, mergePath, interPath)
