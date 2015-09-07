import os, arcpy, common

def pointJSON(point):
  part = point.getPart()
  return {u'type' : u'Point', u'coordinates' : [part.X, part.Y]}

def multiPointJSON(multipoint):
  return {u'type' : u'MultiPoint', u'coordinates' : [[point.X, point.Y] for point in multipoint]}

def polylineJSON(polyline):
  geom = [[[point.X, point.Y] for point in part] for part in polyline]
  if len(geom) == 1:
    return {u'type' : 'LineString', u'coordinates' : geom[0]}
  else:
    return {u'type' : 'MultiLineString', u'coordinates' : geom}

def polygonJSON(polygon):
  geom = []
  partI = 0
  partN = polygon.partCount
  while partI < partN:
    partGeom = [[]]
    part = polygon.getPart(partI)
    point = part.next()
    while point:
      # common.message(point)
      partGeom[-1].append([point.X, point.Y])
      point = part.next()
      if not point: # interior ring (hole)
        partGeom.append([])
        point = part.next()
    if partGeom[-1] == []:
      partGeom = partGeom[:-1]
    geom.append(partGeom)
    partI += 1
  if len(geom) == 1:
    return {u'type' : 'Polygon', u'coordinates' : geom[0]}
  else:
    return {u'type' : 'MultiPolygon', u'coordinates' : geom}


class JSONTransformer:
  START = '{"type" : "FeatureCollection", "features" : ['
  END = ']}'
  JOINER = ','

  def __init__(self, layer, fields=[], precision=None):
    self.layer = layer
    if not precision: precision = '2'
    self.floatFormatter = (u'%i' if precision == '0' else u'%.{}f'.format(precision))
    self.description = arcpy.Describe(self.layer)
    if hasattr(self.description, 'shapeFieldName'):
      self.shapeFld = self.description.shapeFieldName
      self.getGeometry = {u'Point' : pointJSON, u'MultiPoint' : multiPointJSON, u'Polyline' : polylineJSON, u'Polygon' : polygonJSON}[self.description.shapeType]
    else:
      self.shapeFld = None
    self.fields = fields
  
  def getFeatures(self):
    common.progress('opening layer')
    count = common.count(self.layer)
    cursor = arcpy.SearchCursor(self.layer)
    prog = common.progressor('converting', count)
    for row in cursor:
      now = {u'type' : u'Feature', u'properties' : self.getProperties(row)}
      if self.shapeFld is not None:
        now[u'geometry'] = self.getGeometry(row.getValue(self.shapeFld))
      yield now
      prog.move()
    prog.end()
  
  def getProperties(self, row):
    props = {}
    for field in self.fields:
      props[field] = row.getValue(field)
    return props
  
  def output(self, file, encoding='utf8'):
    file.write(self.START)
    start = True
    for featDict in self.getFeatures():
      if not start:
        file.write(self.JOINER)
      else:
        start = False
      file.write(self.toString(featDict).encode(encoding))
    file.write(self.END)
    
  
  # @staticmethod
  # def toString(object):
    # return json.dumps(object, separators=(',', ':')).replace("'", '"')

  # obsolete methods (fail for large datasets)
  def getDict(self):
    return {u'type' : 'FeatureCollection', u'features' : list(self.getFeatures())}
  
  def getString(self):
    return self.toString(self.getDict())
    
  def toString(self, object):
    if isinstance(object, str):
      return u'"' + object.decode('utf8') + u'"'
    elif isinstance(object, unicode):
      return u'"' + object + u'"'
    elif isinstance(object, float):
      return self.floatFormatter % object
    elif isinstance(object, list):
      return u'[' + u','.join([self.toString(sub) for sub in object]) + u']'
    elif isinstance(object, dict):
      return u'{' + u','.join([self.toString(key) + u':' + self.toString(value) for key, value in object.items()]) + u'}'
    elif object is None:
      return u'null'
    else:
      return unicode(str(object))


with common.runtool(4) as parameters:
  layerName, target, fields, precision = parameters
  transformer = JSONTransformer(layerName, fields.split(';'), precision=precision)
  with open(target, 'w') as outfile:
    transformer.output(outfile)
