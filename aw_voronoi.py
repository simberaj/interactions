import sys, os, arcpy, math
sys.path.append('.')
import common

TMP_CIRCPTS = 'tmp_circ'
TMP_ALLPOLY = 'tmp_voroall'

with common.runtool(7) as parameters:
  common.progress('parsing attributes')
  ## GET AND PREPARE THE ATTRIBUTES
  # obtained from the tool input
  points, ptsIDFld, weightFld, normStr, transferFldsStr, tolerStr, outPath = parameters
  location, outName = os.path.split(outPath)
  normalization = math.sqrt(common.toFloat(normStr, 'normalization value') / math.pi)
  tolerance = common.toFloat(tolerStr, 'positional tolerance value')
  transferFlds = common.parseFields(transferFldsStr)
  
  common.progress('creating weighting layer')
  common.overwrite(True)
  circLayer = common.createFeatureClass(os.path.join(location, TMP_CIRCPTS), crs=points)
  inShpFld = arcpy.Describe(points).ShapeFieldName
  circShapeFld = arcpy.Describe(circLayer).ShapeFieldName
  arcpy.AddField_management(circLayer, ptsIDFld, common.outTypeOfField(points, ptsIDFld))
  
  inCount = common.count(points)
  common.progress('opening weighting layer')
  inCur = arcpy.SearchCursor(points)
  outCur = arcpy.InsertCursor(circLayer)
  prog = common.progressor('weighting points', inCount)
  pi2 = 2 * math.pi
  for inRow in inCur:
    # load input geometry
    pt = inRow.getValue(inShpFld).getPart(0)
    id = inRow.getValue(ptsIDFld)
    coor = (pt.X, pt.Y)
    # load radius
    radius = math.sqrt(inRow.getValue(weightFld)) * normalization
    print inRow.getValue(weightFld), radius, normalization
    ptCount = max(int(pi2 * radius / tolerance), 3)
    delta = pi2 / ptCount
    angle = 0
    while angle < pi2:
      outRow = outCur.newRow()
      outRow.setValue(circShapeFld, arcpy.Point(coor[0] + radius * math.cos(angle), coor[1] + radius * math.sin(angle)))
      outRow.setValue(ptsIDFld, id)
      outCur.insertRow(outRow)
      angle += delta
    prog.move()
  del inCur, outCur, inRow, outRow
  prog.end()
  common.progress('building voronoi polygons')
  singlePolys = common.featurePath(location, TMP_ALLPOLY)
  mergedPolys = common.featurePath(location, outName)
  arcpy.CreateThiessenPolygons_analysis(circLayer, singlePolys, 'ALL')
  common.progress('dissolving to weighted polygons')
  arcpy.Dissolve_management(singlePolys, mergedPolys, ptsIDFld)
  common.progress('joining transfer fields')
  arcpy.JoinField_management(mergedPolys, ptsIDFld, points, ptsIDFld, transferFlds)
  common.progress('deleting temporary files')
  common.delete(singlePolys)
  