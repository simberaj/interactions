import sys, os, arcpy
sys.path.append('.')
import common

class ConversionError(Exception):
  pass

class FieldError(ConversionError):
  pass
    

class FieldMapper(object):
  TMP_ID_FLD = 'TMP_ID'
  TMP_ID_TYPE = 'LONG'
  shapeType = None
  shapeFieldName = None
  outputShapeFieldName = None

  def __init__(self, source):
##    common.debug('mapping on ' + str(source))
    self.source = source
    self.fieldTypes = common.fieldTypeList(self.source)
    self.mappings = []
    self.joinIDFields = []
    self.removeSrcFields = []
    self.data = {}
    self.idFld = None
    self.shape = False
    self.errors = 0
  
  def addIDField(self, name, alias=None, transfer=True, check=True):
    if transfer:
      self.addMapField(name, alias)
    elif check and name not in self.fieldTypes:
      raise FieldError, 'field %s not found in %s' % (name, self.source)
    self.idFld = name
  
  def setIDTransfer(self, transfer, alias=None):
    if transfer:
      self.addMapField(self.idFld, alias)
    else:
      self.removeMapField(self.idFld)
      if self.idFld not in self.fieldTypes:
        raise FieldError, 'field %s not found in %s' % (self.idFld, self.source)
  
  def loadShapeField(self, type=None):
    desc = arcpy.Describe(self.source)
    if type is None:
      type = str(desc.shapeType.upper())
    self.shape = True
    self.shapeFieldName = desc.ShapeFieldName
    self.shapeType = type
    # self.mappings.append((self.shapeFieldName, common.SHAPE_KEY, type))

  def removeMapField(self, name):
    for i in range(len(self.mappings)):
      if self.mappings[i][0] == name:
        self.mappings.pop(i)
        return
  
  def addSrcRemoveField(self, name):
    self.removeSrcFields.append(name)
  
  def getMappingDict(self):
    outDict = {}
    for name, alias, type in self.mappings:
      outDict[name] = alias
    return outDict
  
  def hasShape(self):
    return self.shape
  
  def getShapeType(self):
    return self.shapeType
  
  def getCRS(self):
    return self.source
  
  def getIntIDField(self, setID=False, unmapPrevious=False, progressor=None):
    if self.idFld is not None and self.idFld in common.fieldList(self.source, type=common.INT_FIELD_DESCRIBE):
      common.debug('integer field found')
      if progressor is not None: progressor.end()
      return self.idFld
    else:
      tmpFld = self.createTempIDFld(progressor)
      self.addSrcRemoveField(tmpFld)
      if setID:
        if unmapPrevious:
          self.removeMapField(self.idFld)
        self.addIDField(tmpFld, transfer=False, check=False)
      return tmpFld
  
  def createTempIDFld(self, progressor=None):
    arcpy.AddField_management(self.source, self.TMP_ID_FLD, self.TMP_ID_TYPE)
    i = 1
    rows = arcpy.UpdateCursor(self.source)
    for row in rows:
      row.setValue(self.TMP_ID_FLD, i)
      rows.updateRow(row)
      i += 1
      if progressor is not None: progressor.move()
    del rows
    if progressor is not None: progressor.end()
    return self.TMP_ID_FLD

  def loadData(self, progressor=None):
    cursor = arcpy.SearchCursor(self.source)
    names = self.getMappingDict()
    for row in cursor:
      id = row.getValue(self.idFld)
      self.data[id] = {}
      for name in names:
        val = row.getValue(name)
        self.data[id][name] = val
      if self.shape:
        self.data[id][common.SHAPE_KEY] = self.parseShape(row.getValue(self.shapeFieldName))
      if progressor is not None: progressor.move()
    del row, cursor
    if progressor is not None: progressor.end()
    
  def parseShape(self, geom):
    if self.shapeType == 'POINT':
      return geom.getPart()
    else:
      return geom
  
  def open(self, output):
    self.mapDict = self.getMappingDict()
    for name, aliases, outType in self.mappings:
      for alias in aliases:
        arcpy.AddField_management(output, alias, outType)
    outDesc = arcpy.Describe(output)
    if hasattr(outDesc, 'ShapeFieldName'):
      self.outputShapeFieldName = outDesc.ShapeFieldName
      
  def close(self):
    if self.removeSrcFields:
      arcpy.DeleteField_management(self.source, self.removeSrcFields)
  
  def getErrorCount(self):
    return self.errors

      
class LinkFieldMapper(FieldMapper):
  def addMapField(self, name, alias=None):
    if name not in self.fieldTypes:
      raise FieldError, 'field %s not found in %s' % (name, self.source)
    self.mappings.append((name, [(name if alias is None else alias)], common.describeToField(self.fieldTypes[name])))
    
  def remap(self, inRow, outRow, processor=None):
    for name in self.mapDict:
      for alias in self.mapDict[name]:
        outRow.setValue(alias, inRow.getValue(name))
    return outRow

    
class ODFieldMapper(FieldMapper):
  excludeSelf = False

  def setJoinIDFields(self, ids):
    self.joinIDFields = ids
  
  def setJoinIDGetter(self, field, getter):
    self.joinIDSourceField = field
    self.joinIDGetter = getter
  
  def excludeSelfInteractions(self, excludeSelf):
    self.excludeSelf = excludeSelf
  
  def addMapField(self, name, aliases=None):
    if name not in self.fieldTypes:
      raise FieldError, 'field %s not found in %s' % (name, self.source)
    if aliases is None:
      aliases = (common.ORIGIN_MARKER + name, common.DESTINATION_MARKER + name)
    self.mappings.append((name, aliases, common.describeToField(self.fieldTypes[name])))

  def getIDs(self, inRow):
    if self.joinIDFields:
      return tuple(inRow.getValue(idFld) for idFld in self.joinIDFields)
    elif self.joinIDSourceField:
      return self.joinIDGetter(inRow.getValue(self.joinIDSourceField))
    else:
      raise FieldError, 'join IDs not specified'
    
  def remap(self, inRow, outRow, processor=None):
    odData = []
    ids = self.getIDs(inRow)
    if self.excludeSelf and len(ids) > len(frozenset(ids)):
      return None
    for i in range(len(ids)):
      try:
        data = self.data[ids[i]]
      except KeyError:
        return None
      for name in self.mapDict:
        outRow.setValue(self.mapDict[name][i], data[name])
      odData.append(data)
    if processor and odData:
      shape = processor(inRow, odData)
      if shape is None:
        self.errors += 1
      else:
        outRow.setValue(self.outputShapeFieldName, shape)
    return outRow


class Converter:
  def __init__(self, location=None, **kwargs):
    common.progress('initializing paths')
    if location:
      self.location = common.checkFile(location)
  
  def folderPath(self, file):
    return os.path.join(common.folder(self.location), file)
  
  def path(self, file):
    return os.path.join(self.location, file)
    
  def tablePath(self, file):
    return common.tablePath(self.location, file)
    
  def createTable(self, outName):
    return common.createTable(os.path.join(self.location, outName))
    # return arcpy.CreateTable_management(self.location, common.tableName(self.location, outName)).getOutput(0)

  def createFeatureClass(self, outName, type, crs):
    # raise RuntimeError, (('%s ' * 4) % (self.location, outName, type, crs))
    return common.addFeatureExt(arcpy.CreateFeatureclass_management(self.location, outName, type, spatial_reference=crs).getOutput(0))

  def open(self, output, mappers):
    common.progress('preparing output')
    for mapper in mappers:
      mapper.open(output)
      
  def remapData(self, source, output, mappers=[], shapeProcessor=None):
    prog = common.progressor('remapping records', common.count(source))
    inCur = arcpy.SearchCursor(source)
    outCur = arcpy.InsertCursor(output)
    for inRow in inCur:
      outRow = outCur.newRow()
      for mapper in mappers:
        outRow = mapper.remap(inRow, outRow, shapeProcessor)
        if outRow is None:
          break
      if outRow is not None:
        outCur.insertRow(outRow)
      prog.move()
    prog.end()
    del inCur, inRow, outCur, outRow
  
  def setOutput(self, output, paramIndex=None):
    if paramIndex is not None:
      common.setParameter(paramIndex, output)

      
class SpatialMatrixNeighbourLinker(Converter):
  NEIGH_ID_FLD = 'NID'
  SWM_FILE_NAME = 'tmp_swmf.swm'
  TABLE_FILE_NAME = 'tmp_swmt'

  def __init__(self, zones, zoneIDFld, method, location, **kwargs):
    zones = common.toFeatureClass(common.checkFile(zones))
    if not location:
      location = common.location(zones)
    Converter.__init__(self, location, **kwargs)
    self.zones = zones
    self.zoneMapper = ODFieldMapper(self.zones)
    self.zoneMapper.addIDField(zoneIDFld, [common.NEIGH_FROM_FLD, common.NEIGH_TO_FLD], transfer=True)
    self.method = method
    self.tmpTable = self.tablePath(self.TABLE_FILE_NAME)
    self.swmFile = self.folderPath(self.SWM_FILE_NAME)
    common.overwrite(True)
 
  def process(self):
    # check if ID is integer - if not, create an integer field
    count = common.count(self.zones)
    idFld = self.zoneMapper.getIntIDField(setID=True, unmapPrevious=False, progressor=common.progressor('creating temporary IDs', count))
    self.zoneMapper.loadData(common.progressor('loading zone data', count))
    # generate SWM file
    common.progress('generating spatial matrix')    
    arcpy.GenerateSpatialWeightsMatrix_stats(self.zones, idFld, self.swmFile, self.method)
    common.progress('converting matrix to table')
    arcpy.ConvertSpatialWeightsMatrixtoTable_stats(self.swmFile, self.tmpTable)
    self.zoneMapper.setJoinIDFields([idFld, self.NEIGH_ID_FLD])
    
  def output(self, outName, paramIndex=None):
    output = self.createTable(outName)
    self.open(output, [self.zoneMapper])
    self.remapData(self.tmpTable, output, [self.zoneMapper])
    self.setOutput(output, paramIndex)
    return output

  def close(self):
    try:
      self.zoneMapper.close()
      os.unlink(self.swmFile)
      arcpy.Delete_management(self.tmpTable)
    except:
      pass

      
class PolygonToPointConverter(Converter):
  def __init__(self, polygons, inside=False, idFld=None, mapping=None, **kwargs):
    Converter.__init__(self, **kwargs)
    self.polygons = common.checkFile(polygons)
    self.inside = inside
    # if mapping:
      # self.mapper = LinkFieldMapper(self.polygons)
      # if idFld:
        # self.mapper.addIDField(idFld, alias=(mapping[idFld] if mapping and idFld in mapping else None))
      # if mapping:
        # for fld, alias in mapping.iteritems():
          # if fld != idFld:
            # self.mapper.addMapField(fld, alias)
    # else:
      # self.mapper = None
  
  def convert(self, target):
    # if self.mapper:
      # self.open(target, [self.mapper])
      # self.remapData(self.polygons, target, [self.mapper])
    arcpy.FeatureToPoint_management(self.polygons, target, ('INSIDE' if self.inside else 'CENTROID'))
  
def generateNeighbourTableFor(source, idFld, targetName=None, method='CONTIGUITY_EDGES_ONLY'):
  if targetName is None:
    targetName = os.path.splitext(os.path.basename(source))[0] + '_neigh'
  linker = SpatialMatrixNeighbourLinker(source, idFld, method, os.path.dirname(source))
  linker.process()
  output = linker.output(targetName)
  linker.close()
  return output