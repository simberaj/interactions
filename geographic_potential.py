import os, arcpy, numpy, math, common

with common.runtool(7) as parameters:
  points, valueField, extent, cellSizeStr, decay, distLimitStr, output = parameters
  decayCoef = common.toFloat(decay, 'distance decay exponent')
  cellSize = common.toFloat(cellSizeStr, 'cell size')
  
  ## LOAD POINTS and their values
  common.progress('loading points')
  pointList = []
  shapeFld = arcpy.Describe(points).ShapeFieldName
  pointCur = arcpy.SearchCursor(points)
  for row in pointCur:
    geom = row.getValue(shapeFld).getPart()
    val = row.getValue(valueField)
    if val is not None:
      pointList.append((geom.Y, geom.X, float(val)))
  del row, pointCur, geom
  
  ## CREATE RASTER
  # calculate row and column counts
  extVals = [common.toFloat(val, 'extent value') for val in extent.split()]
  extR = abs(extVals[3] - extVals[1])
  extC = abs(extVals[2] - extVals[0])
  rowCount = int(round(extR / float(cellSize)))
  colCount = int(round(extC / float(cellSize)))
  # bottom left pixel coordinates minus one pixel
  curX = extVals[1] - cellSize / 2.0
  curY = extVals[0] - cellSize / 2.0
  defCurY = curY
  
  if distLimitStr:
    distLimit = common.toFloat(distLimitStr, 'distance limit')
  else:
    distLimit = extR + extC
  
  ## COUNTING potentials
  prog = common.ProgressBar('calculating potentials', rowCount * colCount)
  values = numpy.zeros((rowCount, colCount), dtype=numpy.float32)
  for i in range(rowCount):
    curX += cellSize
    curY = defCurY
    for j in range(colCount):
      curY += cellSize
      val = 0
      for point in pointList:
        dist = math.hypot((point[0] - curX), (point[1] - curY))
        if dist <= distLimit:
          val += point[2] / dist ** decayCoef
      values[rowCount - i - 1][j] = val
      prog.move()
  prog.end()

  # SAVE raster
  common.progress('saving raster')
  if arcpy.Exists(output):
    arcpy.Delete_management(output)
  outputRaster = arcpy.NumPyArrayToRaster(values, arcpy.Point(extVals[0], extVals[1]), cellSize)
  outputRaster.save(output)
