import os, common, colors, loaders, arcpy

BANDS = ('r', 'g', 'b')


class ColorDecomposer(loaders.FunctionUpdater):
  requiredInputSlots = ['color']
  requiredOutputSlots = BANDS

  @staticmethod
  def translate(inprow={'color' : 'ffffff'}):
    try:
      rgb = colors.hexToRGB(inprow['color'])
    except colors.ColorCodeError, warn: # if invalid color code
      common.warning(warn)
      rgb = colors.BLACK_RGB # black
    return dict(zip(BANDS, rgb))

with common.runtool(4) as parameters:
  zones, colorFld, cellSize, output = parameters
  cellSize = float(cellSize)
  # calculate color band weights from hex data
  common.progress('creating color fields')
  bandFields = {}
  for band in BANDS:
    bandFields[band] = 'TMP_{}0001'.format(band.upper())
  common.progress('calculating color fields')
  ColorDecomposer(zones, {'color' : colorFld}, bandFields).decompose()
  # zoneRows = arcpy.UpdateCursor(zones)
  # for row in zoneRows:
    # code = row.getValue(colorFld)
    # try:
      # color = colors.hexToRGB(code)
    # except colors.ColorCodeError, warn: # if invalid color code
      # common.warning(warn)
      # color = colors.BLACK_RGB # black
    # for i in range(len(BANDS)):
      # row.setValue(bandFields[BANDS[i]], color[i])
    # zoneRows.updateRow(row)
  # del zoneRows
  # convert color band weights to raster
  common.progress('converting to raster')
  main, ext = os.path.splitext(output)
  bandRasters = {}
  for band in BANDS:
    bandRasters[band] = main + '_' + band + '.img'
    arcpy.PolygonToRaster_conversion(zones, bandFields[band], bandRasters[band],
      'MAXIMUM_COMBINED_AREA', '', cellSize)
  # merge R, G, B bands into one - use IMG format to avoid holes where some of the bands is zero
  common.progress('combining color bands')
  common.debug(bandRasters)
  compRaster = main + '_c.img'
  arcpy.CompositeBands_management([bandRasters[band] for band in BANDS], compRaster)
  # and copy... this was more bugproof
  common.progress('creating result')
  arcpy.CopyRaster_management(compRaster, output)
  common.progress('defining result projection')
  arcpy.DefineProjection_management(output, arcpy.Describe(zones).spatialReference)
  # delete temporary mess
  common.progress('deleting temporary fields')
  arcpy.DeleteField_management(zones, bandFields.values())
  common.progress('deleting temporary files')
  common.delete(*(list(bandRasters.values()) + [compRaster]))
