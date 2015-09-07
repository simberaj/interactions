import os, arcpy, common, conversion

class NetworkingError(Exception):
  pass

class NetworkingOutputError(NetworkingError):
  pass

try:
  arcpy.CheckOutExtension('Network')
except:
  raise NetworkingError, 'could not obtain Network Analyst license'


    
class Networker(object):
  locsCalculated = False

  @staticmethod
  def networkMappings(mappingList):
    merged = []
    for item in mappingList:
      merged.append(' '.join(('#' if part is None else str(part)) for part in item))
    return ';'.join(merged)

  @classmethod
  def calculateLocations(cls, network, places, searchDist):
    if not cls.locsCalculated:
      arcpy.CalculateLocations_na(places, network, searchDist, cls.getNetworkSources(network))
      cls.locsCalculated = True
        
  @staticmethod
  def getNetworkSources(network):
    sources = []
    for source in arcpy.Describe(network).sources:
      if source.sourceType == 'EdgeFeature':
        sources.append([source.name, 'SHAPE'])
      else:
        sources.append([source.name, 'NONE'])
    return sources
        

class PlaceLinker(conversion.Converter):
  def __init__(self, location, places, placesIDField, **kwargs):
    conversion.Converter.__init__(self, location, **kwargs)
    self.places = common.checkFile(places)
    self.placesIDField = placesIDField
    self.placeMapper = conversion.ODFieldMapper(self.places)
    self.placeMapper.addIDField(placesIDField)
    
  def addPlaceFields(self, fields):
    for field in fields:
      self.placeMapper.addMapField(field)
      
  def loadPlaces(self):
    self.placeMapper.loadData(common.progressor('loading place data', common.count(self.places)))
  
  def close(self):
    try:
      self.placeMapper.close()
    except:
      pass

      
class ODJoiner(PlaceLinker):
  def __init__(self, table, odIDFields, places, placeIDField, **kwargs):
    PlaceLinker.__init__(self, common.location(table), places, placeIDField, **kwargs)
    self.table = common.checkFile(table)
    self.placeMapper.setJoinIDFields(odIDFields)
  
  def join(self, paramIndex=None):
    self.open(self.table, [self.placeMapper])
    self.mapData(self.table, [self.placeMapper])
    self.setOutput(self.table, paramIndex)

  def mapData(self, table, mappers=[]):
    prog = common.progressor('mapping attributes', common.count(table))
    cur = arcpy.UpdateCursor(table)
    for row in cur:
      for mapper in mappers:
        row = mapper.remap(row, row)
      cur.updateRow(row)
      prog.move()
    del cur, row
    prog.end()
        
        
class TableLinker(PlaceLinker):
  def __init__(self, table, odIDFields, places, placeIDField, location, **kwargs):
    PlaceLinker.__init__(self, location, places, placeIDField, **kwargs)
    self.table = common.checkFile(table)
    self.linkMapper = conversion.LinkFieldMapper(self.table)
    self.placeMapper.setJoinIDFields(odIDFields)
  
  def addLinkFields(self, fields):
    for field in fields:
      self.linkMapper.addMapField(field)
 
  def output(self, outName, paramIndex=None):
    common.progress('creating output file')
    output = self.createFeatureClass(outName, 'POLYLINE', self.placeMapper.getCRS())
    self.open(output, [self.linkMapper, self.placeMapper])
    self.remapData(self.table, output, [self.linkMapper, self.placeMapper], self.getGeometry)
    self.setOutput(output, paramIndex)
  
  def close(self):
    try:
      self.linkMapper.close()
    except:
      pass
    PlaceLinker.close(self)
  
  
class TableInteractionCreator(TableLinker):
  def __init__(self, table, odIDFields, places, placeIDField, location, **kwargs):
    TableLinker.__init__(self, table, odIDFields, places, placeIDField, location, **kwargs)
    self.placeMapper.setIDTransfer(False)
    self.placeMapper.loadShapeField()

  def getGeometry(self, inRow, odData):
    array = arcpy.Array()
    for data in odData:
      array.add(data[common.SHAPE_KEY])
    return array

    
class TableConnectionCreator(TableLinker, Networker):
  PLACES_LAY = 'tmp_places'
  ROUTE_LAY = 'tmp_routes'
  speedup = False
  cachedGeometry = []

  def __init__(self, table, odIDFields, places, placeIDField, location, **kwargs):
    TableLinker.__init__(self, table, odIDFields, places, placeIDField, location, **kwargs)
    self.placeMapper.setIDTransfer(True)
    self.placeIDQPart = common.query(self.places, '[%s] = ', self.placesIDField)
    self.placeFC = self.places
    if not common.isLayer(self.places):
      common.progress('creating place selection layer')
      self.places = arcpy.MakeFeatureLayer_management(self.placeFC, self.PLACES_LAY).getOutput(0)
    
  
  def speedupOn(self, dist):
    self.speedup = True
    self.speedupDistance = dist

  def loadNetwork(self, network, cost, searchDist, mappings=[]):
    common.progress('calculating places\' network locations')
    network = common.checkFile(network)
    self.calculateLocations(network, self.places, searchDist)
    self.mappings = self.networkMappings(common.NET_FIELDS + mappings)
    if self.speedup:
      self.performSpeedup(network, cost)
    common.progress('preparing routing layer')
    self.naLayer = self.makeRouteLayer(network, self.ROUTE_LAY, cost)
    self.routeSublayer = common.sublayer(self.naLayer, 'Routes')

  def performSpeedup(self, network, cost):
    common.progress('preparing speedup search')
    speeder = BulkConnectionCreator(self.placeFC, self.placesIDField, self.location, excludeSelf=True, messenger=common.Messenger(common.getDebugMode()))
    speeder.loadNetwork(network, cost, cutoff=self.speedupDistance)
    common.progress('performing speedup search')
    speeder.loadPlaces()
    speeder.solve()
    common.progress('reading speedup data')
    self.cachedGeometry = speeder.getGeometryDict()
  
  @staticmethod
  def makeRouteLayer(network, name, cost):
    return arcpy.MakeRouteLayer_na(network, name, cost, output_path_shape='TRUE_LINES_WITHOUT_MEASURES').getOutput(0)
    
  def getGeometry(self, inRow, odData):
    ids = tuple(data[self.placesIDField] for data in odData)
    if ids in self.cachedGeometry:
      return self.cachedGeometry[ids]
    else:
      queryParts = []
      for id in ids:
        if isinstance(id, str) or isinstance(id, unicode):
          id = u"'" + id + u"'"
        else:
          id = unicode(id)
        queryParts.append(self.placeIDQPart + id)
      arcpy.SelectLayerByAttribute_management(self.places, 'NEW_SELECTION', ' OR '.join(queryParts))
      arcpy.AddLocations_na(self.naLayer, 'Stops', self.places, common.NET_FIELD_MAPPINGS, '', append='clear')
      try:
        arcpy.Solve_na(self.naLayer)
      except:
        return None
      else:
        self.routeCursor = arcpy.SearchCursor(self.routeSublayer)
        route = self.routeCursor.next()
        return route.shape
  
  def close(self):
    try:
      del self.routeCursor
      arcpy.SelectLayerByAttribute_management(self.places, 'CLEAR_SELECTION')
    except:
      pass
    remapErrors = self.placeMapper.getErrorCount()
    if remapErrors:
      common.warning('Route not found for %i records, setting shape to NULL' % remapErrors)
    TableLinker.close(self)
    
    

class NetworkLinker(PlaceLinker, Networker):
  NA_LAY = 'tmp_na'
  NAME_MAP = 'Name'
  CUTOFF_PREFIX = 'Cutoff_'
  OUT_COST_PREFIX = 'Total_'
  NAME_FIELD_SEPARATOR = ' - '
  naLayer = None

  def __init__(self, places, placesIDField, location, excludeSelf=False, **kwargs):
    PlaceLinker.__init__(self, location, places, placesIDField, **kwargs)
    self.placesIDType = common.pyTypeOfField(self.places, self.placesIDField)
    self.placesIDTypeConv = common.pyStrOfType(self.placesIDType)
    self.placeMapper.setIDTransfer(True)
    self.placeMapper.setJoinIDGetter(self.NAME_MAP, lambda x: tuple(x.split(self.NAME_FIELD_SEPARATOR)))
    self.placeMapper.excludeSelfInteractions(excludeSelf)
  
  def loadNetwork(self, network, cost=None, cutoff=None, numToFind=None, searchDist=None, cutoffFld=None, numToFindFld=None, mappings=[]):
    common.progress('creating routing layer')
    if not numToFind:
      numToFind = common.count(self.places)
    self.naLayer = self.makeNALayer(common.checkFile(network), self.NA_LAY, cost, cutoff, numToFind)
    common.progress('calculating places\' network locations')
    self.calculateLocations(network, self.places, searchDist)
    common.progress('loading places to network')
    # create mappings
    toMappingList = common.NET_FIELDS + [(self.NAME_MAP, self.placesIDField, None)]
    for item in mappings:
      toMappingList.append(item + [None])
    fromMappingList = toMappingList[:]
    if cutoffFld:
      fromMappingList.append((self.CUTOFF_PREFIX + cost, cutoffFld, None))
    if numToFindFld:
      fromMappingList.append((self.NUM_TO_FIND_HEADER, numToFindFld, None))
    # load locations
    arcpy.AddLocations_na(self.NA_LAY, self.OD_SUBLAYERS[0], self.places, self.networkMappings(fromMappingList), '', append='clear')
    arcpy.AddLocations_na(self.NA_LAY, self.OD_SUBLAYERS[1], self.places, self.networkMappings(toMappingList), '', append='clear')
    self.routeSublayer = common.sublayer(self.naLayer, self.OUTPUT_SUBLAYER)
    self.linkMapper = conversion.LinkFieldMapper(self.routeSublayer)
    try:
      self.linkMapper.addMapField(self.OUT_COST_PREFIX + cost, cost)
    except conversion.FieldError:
      raise conversion.FieldError, 'cost attribute %s not found in network dataset' % cost
  
  def solve(self):
    common.progress('solving')
    arcpy.Solve_na(self.naLayer, 'SKIP', 'CONTINUE')
  
  def getGeometryDict(self):
    prog = common.progressor('caching geometries', common.count(self.routeSublayer))
    geomDict = {}
    inCur = arcpy.SearchCursor(self.routeSublayer)
    for inRow in inCur:
      geomDict[self.placeMapper.getIDs(inRow)] = inRow.shape
      prog.move()
    prog.end()
    del inCur, inRow
    return geomDict
  
  def output(self, outName, paramIndex=None):
    common.progress('creating output file')
    output = self.createFeatureClass(outName, 'POLYLINE', self.placeMapper.getCRS())
    self.open(output, [self.linkMapper, self.placeMapper])
    self.remapData(self.routeSublayer, output, [self.linkMapper, self.placeMapper], self.getGeometry)
    self.setOutput(output, paramIndex)
  
  def getGeometry(self, inRow, odData):
    ids = []
    for data in odData:
      ids.append(data[self.placesIDField])
    if len(ids) == len(frozenset(ids)):
      return inRow.shape
    else:
      return None
      
  def addLinkFields(self, fields):
    for field in fields:
      self.linkMapper.addMapField(field)    
  
  def close(self):
    try:
      self.linkMapper.close()
    except:
      pass
    PlaceLinker.close(self)

    
class BulkInteractionCreator(NetworkLinker):
  OUTPUT_SUBLAYER = 'Lines'
  NUM_TO_FIND_HEADER = 'TargetDestinationCount'
  OD_SUBLAYERS = ['Origins', 'Destinations']

  @staticmethod
  def makeNALayer(network, name=None, cost=None, cutoff=None, numToFind=None):
    return arcpy.MakeODCostMatrixLayer_na(network, name, cost, 
      default_cutoff=cutoff, # how far it can go searching
      default_number_destinations_to_find=numToFind, # how many to find, then stop
      accumulate_attribute_name=[cost]).getOutput(0)
    
class BulkConnectionCreator(NetworkLinker):
  OUTPUT_SUBLAYER = 'Routes'
  NUM_TO_FIND_HEADER = 'TargetFacilityCount'
  OD_SUBLAYERS = ['Facilities', 'Incidents']
  
  @staticmethod
  def makeNALayer(network, name, cost=None, cutoff=None, numToFind=None):
    return arcpy.MakeClosestFacilityLayer_na(network, name, cost, 
      default_cutoff=cutoff, # how far it can go searching
      default_number_facilities_to_find=numToFind, # how many to find, then stop
      accumulate_attribute_name=[cost],
      travel_from_to='TRAVEL_FROM',
      output_path_shape='TRUE_LINES_WITHOUT_MEASURES').getOutput(0)

