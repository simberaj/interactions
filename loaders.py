import os, collections, operator, arcpy, objects, common
from xml.etree import cElementTree as eltree

# TODOS
# generator functions for cursors? what for?
# sequential setter? what for?

SHAPE_FIELD = 'shape'

def parsePoint(shape):
  if shape is None:
    return None
  else:
    part = shape.getPart()
    return numpy.array([part.X, part.Y])

SHAPE_CONVERTORS = {'point' : parsePoint}

class ConfigError(Exception):
  pass

class RegionalLoader:
  ZONE_CALLERS = {'assign' : 'getRegionID', 'core' : 'getLesserCoreID', 'exclave' : 'getExclaveFlag', 'color' : 'getColorHex'}
  requiredZoneSlots = ['id']
  requiredInteractionSlots = ['from', 'to']

  def __init__(self, regionalizer=None):
    self.regionalizer = regionalizer
    self.zoneClass = None
    self.makePresets = False
    self.makeInteractions = False
    self.makeNeighbourhood = False
    self.outputs = []
    self.outputTransforms = []
    if self.regionalizer:
      self.loadRequirements()
    
  def loadRequirements(self):
    pass
    
  def sourceOfZones(self, layer, slots, coreQuery=None, targetClass=None):
    self.zoneLayer = layer
    slots = self.checkSlots(slots, self.requiredZoneSlots)
    if 'id' not in slots:
      raise ValueError, 'zone ID field required'
    self.zoneIDSlot = {'id' : slots['id']}
    self.zoneSlots = slots
    self.zoneClass = targetClass
    self.zoneCoreQuery = coreQuery
    self.zoneOutputSlots = {}
    self.zoneOutputCallers = {}
    self.zoneOutputTypes = {}
  
  def sourceOfPresets(self, slots):
    slots = self.checkSlots(slots, {})
    if slots:
      self.makePresets = True
      self.zoneSlots.update(slots)
    
  def sourceOfInteractions(self, layer, slots, where=None):
    self.interLoader = InteractionReader(layer, self.checkSlots(slots, self.requiredInteractionSlots), where=where)
    self.makeInteractions = True
  
  def sourceOfMultiInteractions(self, layer, slots, where=None, ordering=None):
    objects.MultiInteractions.setDefaultLength(len(slots) - 2)
    if self.zoneClass:
      self.zoneClass.interactionClass = objects.MultiInteractions
    if self.regionalizer:
      self.regionalizer.getRegionFactory().interactionClass = objects.MultiInteractions
    self.interLoader = MultiInteractionReader(layer, slots, ordering=ordering, where=where)
    self.makeInteractions = True
  
  def possibleNeighbourhood(self, layer, slots={}):
    if not self.regionalizer or self.regionalizer.neighbourhoodNeeded():
      if not layer:
        layer = self.createNeighbourTable()
      self.makeNeighbourhood = True
      self.neighbourLoader = NeighbourTableReader(layer, slots)
    
  def createNeighbourTable(self):
    global conversion
    import conversion
    return conversion.generateNeighbourTableFor(self.zoneLayer, self.zoneSlots['id'])
    
  def load(self):
    self.zoneLoader = ZoneReader(self.zoneLayer, self.zoneSlots, targetClass=self.zoneClass)
    self.zoneList = self.zoneLoader.read('loading zones')
    if self.makeInteractions:
      self.interLoader.match(self.zoneList, text='loading interactions')
    if self.makeNeighbourhood:
      self.neighbourLoader.match(self.zoneList, text='loading neighbourhood')
    if self.regionalizer:
      if self.makePresets:
        self.regionalizer.initRun(self.zoneList, presets=self.zoneLoader.getPresets())
      else:
        self.regionalizer.initRun(self.zoneList)
  
  def checkSlots(self, slots, required):
    # common.debug(slots)
    todel = []
    for slot in slots:
      if not slots[slot]:
        todel.append(slot)
    for slot in todel:
      del slots[slot]
    # common.debug(slots)
    for slot in required:
      if not (slot in slots and slots[slot]):
        raise ValueError, 'slot {} required'.format(slot)
    return slots
  
  def getInteractionSlots(self):
    return self.interLoader.getSlots()
  
  def getRegionalizer(self):
    return self.regionalizer
  
  def getZoneList(self):
    if self.makePresets:
      return self.regionalizer.getZones()
    else:
      return self.zoneList
  
  def getZoneDict(self):
    if self.makePresets:
      return self.regionalizer.getOutputZones()
    else:
      return {zone.getID() : zone for zone in self.zoneList}

  def addZoneOutputSlot(self, slot, field, require=False):
    if field:
      if slot in self.ZONE_CALLERS:
        self.zoneOutputSlots[slot] = field
        self.zoneOutputCallers[slot] = operator.methodcaller(self.ZONE_CALLERS[slot])
      else:
        prefix = self.zoneOutputSlots['assign'] + '_' if 'assign' in self.zoneOutputSlots else ''
        self.zoneOutputSlots[slot] = prefix + field
        self.zoneOutputCallers[slot] = objects.ZoneMeasurer().measureGetter(slot)
    else:
      if require:
        raise ValueError, 'required zone output field for {} not provided'.format(slot.upper())
  
  def inferZoneTypes(self):
    # print self.zoneList, self.zoneOutputSlots, self.zoneOutputCallers
    self.zoneOutputTypes.update(inferFieldTypes(self.zoneList, self.zoneOutputSlots, callers=self.zoneOutputCallers))
  
  def setOverlapOutput(self, overlapTable):
    self.outputs.append(InteractionWriter(overlapTable, {'value' : 'OVERLAP'}, convertToID=True))
    self.outputTransforms.append(operator.methodcaller('getRegionOverlaps'))
  
  def output(self, regionalizer):
    common.progress('computing outputs')
    regionalizer.postRun()
    common.progress('writing zone output')
    self.inferZoneTypes()
    ObjectMarker(self.zoneLayer, self.zoneIDSlot, self.zoneOutputSlots, self.zoneOutputCallers, self.zoneOutputTypes).mark(regionalizer.getOutputZones())
    # print
    # print regionalizer.getRegionOverlaps()
    # print
    common.progress('writing optional outputs')
    for i in range(len(self.outputs)):
      self.outputs[i].write(self.outputTransforms[i](regionalizer))
  
  
class RowOperator:
  indexOffset = 0

  def __init__(self, slots, constants={}, conversions={}, object=None):
    self.slots = slots
    self.constants = constants
    self.conversions = conversions.items()
    self.object = object

  def setIndexOffset(self, offset):
    self.indexOffset = offset
    
  def setIndexAccess(self, indexAccess):
    self.indexAccess = indexAccess
    self.initSlots()
  
  def initSlots(self):
    fieldSet = set()
    for mapping in self.slots.values():
      fieldSet.update(self.getKeys(mapping))
    self.fieldNames = tuple(fieldSet)
    if self.indexAccess:
      self.fieldIndexes = {self.fieldNames[i] : i + self.indexOffset for i in range(len(self.fieldNames))}
  
  def getFieldNames(self):
    return self.fieldNames

  def getFieldCount(self):
    return len(self.fieldNames)
    
  @staticmethod
  def getKeys(mapping):
    return [mapping] if type(mapping) in (str, unicode) else mapping
  
  def converted(self, values):
    for slot, converter in self.conversions:
      values[slot] = converter(values[slot])
    return values
  
  def addConversion(self, slot, converter):
    self.conversions.append((slot, converter))

class OneFieldGetter(RowOperator):
  def __init__(self, field):
    self.field = field

  def initSlots(self):
    self.get = self.getByIndex if self.indexAccess else self.getByKey
  
  def getByIndex(self, row):
    return row[self.indexOffset]
    
  def getByKey(self, row):
    return row.getValue(self.field)
    
  def getFieldNames(self):
    return [self.field]

  def getFieldCount(self):
    return 1
  
class Getter(RowOperator):
  def initSlots(self):
    RowOperator.initSlots(self)
    self.get = self.getByIndex if self.indexAccess else self.getByKey
    if self.indexAccess:
      self.slotIndexes = {slot : self.fieldIndexes[field] for slot, field in self.slots.iteritems()}
    
  def getByIndex(self, row):
    result = self.constants.copy()
    for slot, index in self.slotIndexes.iteritems():
      result[slot] = row[index]
    result = self.converted(result) if self.conversions else result
    return self.object(**result) if self.object else result
  
  def getByKey(self, row):
    result = self.constants.copy()
    for slot, field in self.slots.iteritems():
      result[slot] = row.getValue(field)
    result = self.converted(result) if self.conversions else result
    return self.object(**result) if self.object else result

      
class Setter(RowOperator):
  def __init__(self, slots, callerNames={}, types={}, **kwargs):
    # print 'SETTER'
    # print types
    RowOperator.__init__(self, slots, **kwargs)
    self.callerNames = callerNames
    self.types = types

  def initSlots(self):
    RowOperator.initSlots(self)
    self.set = self.setByIndex if self.indexAccess else self.setByKey
    self.slotCallers = self.createSlotCallers() # slot -> getting function
    self.fieldCallers = {} # field -> caller
    self.fieldSlots = {} # field -> slot
    staticDict = {}
    for slot, value in self.constants.iteritems():
      for field in self.getKeys(self.slots[slot]):
        staticDict[self.fieldIndexes[field] if self.indexAccess else field] = value
    self.dynamic = []
    for slot, mapping in self.slots.iteritems():
      for field in self.getKeys(mapping):
        key = self.fieldIndexes[field] if self.indexAccess else field
        caller = self.slotCallers[slot]
        if key not in staticDict:
          self.dynamic.append((key, caller))
        self.fieldCallers[field] = caller
        self.fieldSlots[field] = slot
    self.static = staticDict.items()
  
  def createSlotCallers(self):
    # print self.slots, self.callerNames, self.constants, self.object
    slotCallers = {}
    for slot in self.slots.keys():
      if slot in self.constants:
        slotCallers[slot] = common.constantLambda(self.constants[slot])
      elif slot in self.callerNames:
        if hasattr(self.callerNames[slot], '__call__'):
          slotCallers[slot] = self.callerNames[slot]
        else:
          slotCallers[slot] = operator.methodcaller(self.callerNames[slot])
      elif self.object:
        slotCallers[slot] = operator.methodcaller(slot)
      else:
        slotCallers[slot] = operator.itemgetter(slot)
    return slotCallers

  def setByIndex(self, row, values):
    if values is not None:
      values = converted(values) if self.conversions else values
      for index, caller in self.dynamic:
        val = caller(values)
        if val is not None:
          row[index] = val
      for index, constant in self.static:
        row[index] = constant
    return row
  
  def setByKey(self, row, values):
    if values is not None:
      values = converted(values) if self.conversions else values
      for field, caller in self.dynamic:
        val = caller(values)
        if val is not None:
          row.setValue(field, val)
      for field, constant in self.static:
        row.setValue(field, constant)
    return row
    # except KeyError, slot:
      # raise KeyError, 'slot {} value not supplied when writing to {}'.format(slot, self.layer)
  
  def newRow(self, cursor):
    if self.indexAccess:
      return [None] * len(self.fieldNames)
    else:
      return cursor.newRow()
  
  def createFields(self, layer, typePattern, overwrite=True, append=False):
    # print self.fieldsToSlots, typePattern
    fieldList = common.fieldList(layer)
    for field, caller in self.fieldCallers.iteritems():
      fieldFound = bool(field in fieldList)
      if fieldFound:
        if overwrite and not append:
          arcpy.DeleteField_management(layer, field)
        elif not append:
          raise IOError, 'field {} already exists in table {} while overwrite is off'.format(field, layer)
      elif append:
        common.warning('field {} does not exist in table {} while append is on, creating')
      if self.fieldSlots[field] in self.types:
        coltype = self.types[self.fieldSlots[field]]
      else:
        coltype = type(caller(typePattern))
        if coltype is type(None):
          raise ValueError, 'could not infer type for {} slot'.format(self.fieldSlots[field])
      if not (append and fieldFound):
        common.addField(layer, field, coltype)
  
  def getFieldNames(self):
    return self.fieldNames

    
class Retriever:
  def __init__(self, getter, strict=True, default=None):
    self.getter = getter
    self.objects = None
    self.strict = strict
    self.default = default
  
  def feed(self, objects):
    self.objects = objects
  
  def retrieve(self, row):
    try:
      return self.lookup(self.getter.get(row))
    except KeyError:
      if self.strict:
        raise
      else:
        return self.default
  
  def setIndexAccess(self, indexAccess):
    self.getter.setIndexAccess(indexAccess)
  
  def getFieldNames(self):
    return self.getter.getFieldNames()
  
  def getFieldCount(self):
    return self.getter.getFieldCount()

class SequentialRetriever(Retriever):
  def __init__(self, strict=True):
    Retriever.__init__(self, None, strict=strict)
    self.i = -1
  
  def setIndexAccess(self, *args, **kwargs):
    pass
  
  def retrieve(self, row):
    self.i += 1
    try:
      return self.objects[self.i]
    except IndexError:
      if self.strict:
        raise
      else:
        return None
  
  def getFieldNames(self):
    return tuple()
    
  def getFieldCount(self):
    return 0
    
class IDRetriever(Retriever):
  ID_SLOT = 'id'

  def lookup(self, data):
    return self.objects[data[self.ID_SLOT]]

class RelationRetriever(Retriever):
  FROM_SLOT = 'from'
  TO_SLOT = 'to'
  
  def lookup(self, data):
    return self.objects[(data[self.FROM_SLOT], data[self.TO_SLOT])]

class SidelessRelationRetriever(RelationRetriever):
  def lookup(self, data):
    direct = (data[self.FROM_SLOT], data[self.TO_SLOT])
    try:
      return self.objects[direct]
    except KeyError:
      return self.objects[(direct[1], direct[0])]



    
class CursorOperator:
  def __init__(self, layer, useDA=True):
    self.layer = layer
    self.count = 0
    self.usesDA = hasattr(arcpy, 'da') and useDA
    self._description = None
    self.progressor = None

  def getCount(self):
    return self.count
  
  def hasShapeField(self):
    return hasattr(self.getDescription(), 'shapeFieldName')
  
  def getShapeFieldName(self):
    return self.getDescription().shapeFieldName
  
  def getShapeType(self):
    return self.getDescription().shapeType.lower()
  
  def getDescription(self):
    if self._description is None:
      self._description = arcpy.Describe(self.layer)
    return self._description
  
  def move(self):
    if self.progressor:
      self.progressor.move()
    self.count += 1
  
  def end(self):
    if self.progressor:
      self.progressor.end()

  
class ReadCursor(CursorOperator):
  def __init__(self, layer, getter, where=None, sortSlots=[]):
    CursorOperator.__init__(self, layer, useDA=(not sortSlots))
    self.where = where
    self.getter = getter
    self.getter.setIndexAccess(self.usesDA)
    if not self.usesDA and self.hasShapeField():
      self.getter.addConversion(self.getShapeFieldName(), SHAPE_CONVERTORS[self.getShapeType()])
              
  def calibrate(self, row, text=None):
    if text:
      self.progressor = common.progressor(text, common.count(self.layer))
  
  def rows(self, text=None):
    if text:
      common.progress(text)
    if self.usesDA:
      cursor = arcpy.da.SearchCursor(self.layer, self.getter.getFieldNames(), self.where)
    else:
      cursor = arcpy.SearchCursor(self.layer, self.where, '', '', self.sortExpr)
    first = True
    for row in cursor:
      if first:
        self.calibrate(row, text=text)
        first = False
      yield self.getter.get(row)
      self.move()
    del row, cursor
    self.end()
  
    
class WriteCursor(CursorOperator):
  def __init__(self, layer, setter, overwrite=True, append=False, template=None, shapeType=None, crs=None):
    CursorOperator.__init__(self, layer)
    self.setter = setter
    self.overwrite = overwrite
    self.append = append
    self.template = template
    self.crs = crs
    self.shapeType = shapeType
    self.hasShape = not (crs is None and shapeType is None and (template is None or not isFeatureClass(template)))
    if not self.usesDA and shapeType:
      global numpy
      import numpy
      self.setter.addConversion(SHAPE_FIELD, SHAPE_CONVERTORS[shapeType.lower()])
    self.setter.setIndexAccess(self.usesDA)
  
  def write(self, rows, text=None, rowcount=None):
    if rows:
      first = True
      for row in rows:
        if first:
          cursor = self.calibrate(row, text, (len(rows) if rowcount is None else rowcount))
          first = False
        self.writeRow(cursor, row)
        self.move()
      del row
      del cursor
    else:
      common.warning('empty output created: {}'.format(self.layer))
    self.end()
  
  def calibrate(self, row, text=None, count=None):
    # print 'CALIBRATING'
    # print row
    if text:
      self.progressor = common.progressor(text, count)
    self.create(row)
    if self.usesDA:
      return arcpy.da.InsertCursor(self.layer, self.setter.getFieldNames())
    else:
      return arcpy.InsertCursor(self.layer)
    
  def create(self, row):
    if not self.append:
      if self.overwrite:
        arcpy.env.overwriteOutput = True
      if self.hasShape:
        self.layer = common.createFeatureClass(self.layer, self.shapeType, self.template, self.crs)
      else:
        self.layer = common.createTable(self.layer)
    self.setter.createFields(self.layer, row, append=self.append)
  
  def writeRow(self, cursor, values):
    cursor.insertRow(self.setter.set(self.setter.newRow(cursor), values))
      
class UpdateCursor(CursorOperator):
  def __init__(self, layer, retriever, setter, overwrite=True, where=None, constants={}):
    CursorOperator.__init__(self, layer)
    self.overwrite = overwrite
    self.where = where
    self.retriever = retriever
    self.retriever.setIndexAccess(self.usesDA)
    self.setter = setter
    self.setter.setIndexOffset(self.retriever.getFieldCount())
    self.setter.setIndexAccess(self.usesDA)

  def update(self, objects, text=None):
    if objects:
      self.retriever.feed(objects)
      if isinstance(objects, dict):
        pattern = next(objects.itervalues())
      else:
        for pattern in objects: break
      print pattern, text
      cursor = self.calibrate(pattern, text)
      for row in cursor:
        self.updateRow(cursor, row)
        self.count += 1
      del row, cursor
    
  def calibrate(self, row, text=None):
    if self.overwrite:
      arcpy.env.overwriteOutput = True
    if text:
      self.progressor = common.progressor(text, common.count(self.layer))
    self.setter.createFields(self.layer, row, overwrite=self.overwrite)
    if self.usesDA:
      return arcpy.da.UpdateCursor(self.layer, self.retriever.getFieldNames() + self.setter.getFieldNames(), self.where)
    else:
      return arcpy.UpdateCursor(self.layer, self.where)
  
  def updateRow(self, cursor, row):
    # common.message(row)
    # common.message(self.setter.fieldIndexes)
    # common.message(self.setter.fieldNames)
    # common.message(self.setter.dynamic)
    # common.message(self.setter.static)
    # common.message(self.retriever.retrieve(row))
    # raise RuntimeError
    cursor.updateRow(self.setter.set(row, self.retriever.retrieve(row)))

class TranslateCursor(UpdateCursor):
  def __init__(self, layer, getter, setter, where=None, overwrite=True, constants={}):
    CursorOperator.__init__(self, layer)
    self.overwrite = overwrite
    self.where = where
    self.getter = getter
    self.getter.setIndexAccess(self.usesDA)
    self.retriever = self.getter # to mask for field name requests
    self.setter = setter
    self.setter.setIndexOffset(self.getter.getFieldCount())
    self.setter.setIndexAccess(self.usesDA)

  def translate(self, function, text=None):
    if self.overwrite:
      arcpy.env.overwriteOutput = True
    cursor = self.calibrate(function(), text)
    for row in cursor:
      self.translateRow(cursor, row, function)
      self.count += 1
    del row, cursor
  
  def translateRow(self, cursor, row, function):
    cursor.updateRow(self.setter.set(row, function(self.getter.get(row))))
            
class DatasetOperator:
  defaultFields = {}
  requiredInputSlots = {}
  targetClass = None
  
  def __init__(self, layer):
    self.layer = layer

  def createGetter(self, slotDict, constants={}):
    slots = self.prepareSlots(slotDict, self.requiredInputSlots, self.defaultFields)
    return Getter(slots, constants, object=self.targetClass)
    
  def prepareSlots(self, slots, required=[], default={}):
    for slot in required:
      if slot not in slots:
        if slot in default:
          slots[slot] = default[slot]
        else:
          raise ValueError, 'required slot {} not supplied with field name for {}, no default value found'.format(slot, self.layer)
    return slots
    
class DatasetReader(DatasetOperator):
  def __init__(self, layer, targetClass=None):
    DatasetOperator.__init__(self, layer)
    self.targetClass = self.__class__.targetClass if targetClass is None else targetClass

class OneFieldReader(DatasetOperator):
  def __init__(self, layer, field, where=None):
    DatasetOperator.__init__(self, layer)
    self.reader = ReadCursor(layer, OneFieldGetter(field), where=where)
  
  def read(self, text=None):
    return list(self.reader.rows(text=text))
    
class BasicReader(DatasetReader):
  requiredInputSlots = []
  targetClass = dict
  
  def __init__(self, layer, slotDict, targetClass=None, where=None, sortSlots=[]):
    DatasetReader.__init__(self, layer, targetClass=targetClass)
    self.reader = ReadCursor(layer, self.createGetter(slotDict), where=where, sortSlots=sortSlots)

  def read(self, text=None):
    return list(self.reader.rows(text=text))
    
class DictReader(DatasetReader):
  requiredInputSlots = ['id']

  def __init__(self, layer, slotDict, where=None, sortSlots=[]):
    DatasetReader.__init__(self, layer)
    self.reader = ReadCursor(layer, self.createGetter(slotDict), where=where, sortSlots=sortSlots)
  
  def read(self, text=None):
    out = {}
    for row in self.reader.rows(text=text):
      out[row['id']] = row
    return out
    
    
class ZoneReader(DatasetReader):
  requiredInputSlots = ['id']
  targetClass = None
  presetClass = objects.AssignmentPreset
  coreDiffSlot = 'coreable'
  presetSlots = collections.OrderedDict([('coop', True), ('assign', False)])
  
  def __init__(self, layer, slotDict, targetClass=None, coreQuery=None):
    # common.debug(slotDict)
    DatasetReader.__init__(self, layer)
    self.zoneClass = objects.FlowZone if targetClass is None else targetClass
    self.presetsOn = False
    if coreQuery:
      coreGetter = self.createGetter(slotDict, constants={self.coreDiffSlot : True})
      hinterGetter = self.createGetter(slotDict, constants={self.coreDiffSlot : False})
      self.readers = [ReadCursor(layer, coreGetter, where=coreQuery),
        ReadCursor(layer, hinterGetter, where=common.invertQuery(coreQuery))]
    else:
      self.readers = [ReadCursor(self.layer, self.createGetter(slotDict))]
    self.presets = []

  def prepareSlots(self, slots, required=[], default={}):
    slots = DatasetReader.prepareSlots(self, slots, required, default)
    self.usedPresetSlots = []
    # determine if presets are to be loaded
    for slot in self.presetSlots:
      if slot in slots:
        self.presetsOn = True
        self.usedPresetSlots.append(slot)
    return slots
    
  def getPresets(self):
    return self.presets
 
  def savePreset(self, row):
    doSave = True
    for slot in self.usedPresetSlots:
      if doSave and row[slot]:
        self.presets.append(self.presetClass(row['id'], row[slot], self.presetSlots[slot]))
        doSave = False
      del row[slot]
    return row
        
  def read(self, text='loading zones'):
    zones = []
    for reader in self.readers:
      for row in reader.rows(text=text):
        if self.presetsOn:
          row = self.savePreset(row)
        zones.append(self.zoneClass(**row))
    return zones
  
  
class MatchReader(DatasetReader):
  DEFAULT_ID_GETTER = operator.methodcaller('getID')

  def __init__(self, layer, slotDict, targetClass=None, where=None):
    DatasetReader.__init__(self, layer, targetClass)
    self.reader = ReadCursor(self.layer, self.createGetter(slotDict), where=where)
    self.fails = 0
  
  def fail(self):
    self.fails += 1
  
  def failWarning(self):
    if self.fails:
      common.warning('{} {} failed to match, {}'.format(self.fails, self.containsWhat, self.handledFails))
  
class RelationReader(MatchReader):
  DEFAULT_FROM_SETTER_NAME = 'setOutflows'
  DEFAULT_TO_SETTER_NAME = 'setInflows'
  requiredInputSlots = ('from', 'to')
  twosided = True

  def __init__(self, layer, slotDict={}, relationClass=None, where=None):
    MatchReader.__init__(self, layer, slotDict, relationClass, where=where)
    if self.twosided:
      self.default = lambda: (self.relationClass(), self.relationClass())
    else:
      self.default = lambda: self.relationClass()
      
  def read(self, text=None):
    relations = collections.defaultdict(self.default)
    for row in self.reader.rows(text=text):
      self.addRelation(relations, row)
    return relations

  def match(self, objects, idGetter=None, fromSetterName=None, toSetterName=None, setFrom=True, setTo=None, text=None):
    idGetter = self.DEFAULT_ID_GETTER if idGetter is None else idGetter
    fromSetterName = self.DEFAULT_FROM_SETTER_NAME if fromSetterName is None else fromSetterName
    toSetterName = self.DEFAULT_TO_SETTER_NAME if toSetterName is None else toSetterName
    setTo = self.setTo if setTo is None else setTo
    relations = self.read(text=text)
    objectDict = {idGetter(obj) : obj for obj in objects}
    for id in objectDict:
      relTuple = relations[id]
      if self.twosided:
        if setFrom:
          outflows = self.remapTargets(objectDict, relTuple[0])
          getattr(objectDict[id], fromSetterName)(outflows)
        if setTo:
          inflows = self.remapTargets(objectDict, relTuple[1])
          getattr(objectDict[id], toSetterName)(inflows)
      else:
        flows = self.remapTargets(objectDict, relTuple)
        getattr(objectDict[id], fromSetterName)(flows)
    self.failWarning()
  
class InteractionReader(RelationReader):
  relationClass = objects.Interactions
  requiredInputSlots = RelationReader.requiredInputSlots + ('value', )
  setTo = True
  containsWhat = 'interactions'
  handledFails = 'used as unknown (raw) flows'
  
  def addRelation(self, relations, row):
    relations[row['from']][0][row['to']] += row['value']
    relations[row['to']][1][row['from']] += row['value']
  
  def remapTargets(self, objectDict, relation):
    remapped = relation.new()
    for id, value in relation.iteritems():
      if id in objectDict:
        remapped[objectDict[id]] = value
      else:
        remapped.addRaw(value)
        self.fail()
    return remapped

    
class MultiInteractionReader(InteractionReader):
  relationClass = objects.MultiInteractions
  requiredInputSlots = RelationReader.requiredInputSlots
  
  def __init__(self, layer, slotDict={}, ordering=None, **kwargs):
    InteractionReader.__init__(self, layer, slotDict, **kwargs)
    if ordering is None:
      ordering = slotDict.keys()
      ordering.remove('from')
      ordering.remove('to')
    self.ordering = ordering
    global numpy
    import numpy
  
  def addRelation(self, relations, row):
    relvec = numpy.array([row[slot] for slot in self.ordering])
    relations[row['from']][0][row['to']] += relvec
    relations[row['to']][1][row['from']] += relvec
  
class OverlapReader(RelationReader):
  relationClass = collections.defaultdict
  twosided = False
  setTo = False
  requiredInputSlots = RelationReader.requiredInputSlots + ('value', )
  containsWhat = 'overlaps'
  handledFails = 'undefined'
    
  def addRelation(self, relations, row):
    relations[row['from']][row['to']] = row['value']
    
class NeighbourTableReader(RelationReader):
  relationClass = list
  twosided = False
  setTo = False
  defaultFields = {'from' : 'ID_FROM', 'to' : 'ID_TO'}
  containsWhat = 'neighbourhood relations'
  handledFails = 'ignored'
  DEFAULT_FROM_SETTER_NAME = 'setNeighbours'
  
  def addRelation(self, relations, row):
    relations[row['from']].append(row['to'])
  
  def remapTargets(self, objectDict, relation):
    remapped = []
    for id in relation:
      if id in objectDict:
        remapped.append(objectDict[id])
      else:
        self.fail()
    return remapped

        
class AdditiveReader(MatchReader):
  targetClass = None
  requiredInputSlots = ('id', )

  def match(self, objects, idGetter=None, setterName=None, text=None):
    idGetter = self.DEFAULT_ID_GETTER if idGetter is None else idGetter
    setter = operator.methodcaller(self.DEFAULT_SETTER_NAME if setterName is None else setterName)
    additions = self.read(text=text)
    for obj in objects:
      id = idGetter(obj)
      if id in additions:
        setter(obj, **additions[id])
      else:
        self.fail()
  
  def read(self, text=None):
    additions = {}
    for row in self.reader.rows(text=text):
      self.additions[row['id']] = row
    return additions
        
class PointGeometryReader(AdditiveReader):
  containsWhat = 'point geometries'
  handledFails = 'ignored'
 
 
class RelationWriter(DatasetOperator):
  REQUIRED_SLOTS = ('from', 'to')
  DEFAULT_FIELDS = {'from' : 'ID_FROM', 'to' : 'ID_TO'}

  def __init__(self, layer, slotDict, convertToID=False, append=False):
    self.layer = layer
    self.convertToID = convertToID
    # if convertToID:
      # self.fromtoConverter = operator.methodcaller('getID')
    # else:
      # self.fromtoConverter = None
    self.slotDict = self.prepareSlots(slotDict, self.REQUIRED_SLOTS, self.DEFAULT_FIELDS)
    self.writer = WriteCursor(self.layer, Setter(self.slotDict), append=append)
  
  def write(self, relations, text=None):
    self.writer.write(self.objectRelationsToRows(relations) if self.convertToID else self.relationsToRows(relations), text=text)
  
  def saveRelations(self, relations):
    self.write(relations)
  
  def getSlots(self):
    return self.slotDict
  
class InteractionWriter(RelationWriter):
  def relationsToRows(self, relations):
    rels = []
    for source, relation in relations.iteritems():
      for target, value in relation.iteritems():
        rels.append(self.rowFactory(source, target, value))
    return rels
  
  def objectRelationsToRows(self, relations):
    conv = operator.methodcaller('getID')
    rels = []
    for source, relation in relations.iteritems():
      source = conv(source)
      for target, value in relation.iteritems():
        rels.append(self.rowFactory(source, conv(target), value))
    return rels
  
  def rowFactory(self, source, target, value):
    return {'from' : source, 'to' : target, 'value' : value}
        
class MultiInteractionWriter(InteractionWriter):
  def __init__(self, layer, slotDict, **kwargs):
    InteractionWriter.__init__(self, layer, slotDict, **kwargs)
    self.valueSlots = slotDict.values()
    self.valueSlots.remove(slotDict['from'])
    self.valueSlots.remove(slotDict['to'])
    
  def rowFactory(self, source, target, value):
    res = {'from' : source, 'to' : target}
    for i in range(len(self.valueSlots)):
      res[self.valueSlots[i]] = value[i]
    return res
        
class Marker(DatasetOperator):
  maxSlots = None
  defaultSlots = {}
  strictRetrieve = True
  defaultRow = None
  requiredOutputSlots = {}

  def __init__(self, layer, inSlots, outSlots, outCallers={}, outTypes={}, where=None):
    DatasetOperator.__init__(self, layer)
    self.updater = UpdateCursor(layer, self.retrieverClass(self.createGetter(inSlots), strict=self.strictRetrieve, default=self.defaultRow), self.createSetter(outSlots, outCallers, outTypes), where=where)
    # common.message(inSlots)
    # common.message(outSlots)
  
  def mark(self, objects, text=None):
    self.updater.update(objects, text=text)

  def createSetter(self, outSlots, outCallers, outTypes):
    if self.maxSlots is not None and len(outSlots) > self.maxSlots:
      raise ValueError, 'too many output slots'
    return Setter(self.prepareSlots(outSlots, self.requiredOutputSlots, default=self.defaultSlots), outCallers, outTypes)

class ObjectMarker(Marker):
  requiredInputSlots = ['id']
  retrieverClass = IDRetriever
        
class ColorMarker(ObjectMarker):
  requiredOutputSlots = ['color']
  defaultSlots = {'color' : 'COLOR'}
  strictRetrieve = False
  
  class PseudoColorZone:
    def getColor(self):
      return 'ffffff'
      
  defaultRow = PseudoColorZone()
  
  
        
class RelationMarker(Marker):
  requiredInputSlots = ('from', 'to')
  retrieverClass = RelationRetriever
  
  def mark(self, relations, text=None):
    # common.message(dict([relations.items()[0]]))
    # common.message(self.relationsToRows(dict([relations.items()[0]])))
    self.updater.update(self.relationsToRows(relations), text=text)
  

class OverlapMarker(RelationMarker):
  requiredInputSlots = ('from', 'to')
  requiredOutputSlots = tuple()
  strictRetrieve = False
  retrieverClass = SidelessRelationRetriever
  
  def relationsToRows(self, relations):
    rowDict = {}
    for source, relation in relations.iteritems():
      for target, value in relation.iteritems():
        rowDict[(source, target)] = value
    return rowDict
    
class InteractionTwosideMarker(RelationMarker):
  requiredInputSlots = ('from', 'to')
  requiredOutputSlots = ('in', 'out')
  maxSlots = 2

  def relationsToRows(self, relations):
    rowDict = collections.defaultdict(lambda: {'in' : 0, 'out' : 0})
    for source, relation in relations.iteritems():
      for target, value in relation[0].iteritems(): # appears as an outflow
        rowDict[(source, target)]['out'] = value
      for target, value in relation[1].iteritems(): # appears as an inflow
        rowDict[(target, source)]['in'] = value
    return rowDict
  
class InteractionPresenceMarker(RelationMarker):
  requiredInputSlots = ('from', 'to')
  requiredOutputSlots = ('in', 'out')
  maxSlots = 2
  defaultSlots = {'in' : 'IS_IN', 'out' : 'IS_OUT'}
      
  def relationsToRows(self, relations):
    rowDict = collections.defaultdict(lambda: {'in' : 0, 'out' : 0})
    for source, relation in relations.iteritems():
      for target, value in relation[0].iteritems(): # appears as an outflow
        rowDict[(source, target)]['out'] = 1
      for target, value in relation[1].iteritems(): # appears as an inflow
        rowDict[(target, source)]['in'] = 1
    return rowDict

    
class FunctionUpdater(DatasetOperator):
  def __init__(self, layer, inSlots, outSlots, overwrite=True, where=None):
    DatasetOperator.__init__(self, layer)
    self.overwrite = overwrite
    self.translator = TranslateCursor(layer, self.createGetter(inSlots), Setter(self.prepareSlots(outSlots, self.requiredOutputSlots)), where=where)
  
  def decompose(self, text=None):
    self.translator.translate(self.translate, text=text)
    

class SequentialUpdater(DatasetOperator):
  requiredOutputSlots = {}

  def __init__(self, layer, outSlots, where=None):
    DatasetOperator.__init__(self, layer)
    self.updater = UpdateCursor(layer, SequentialRetriever(), Setter(self.prepareSlots(outSlots, self.requiredOutputSlots)), where=where)
  
  def update(self, data, text=None):
    self.updater.update(data, text=text)
    
class ConfigReader:
  VERSION = None
  FILE_PURPOSE = 'unknown'
  ROOT_TAG_NAME = 'unknown'

  def __init__(self, parameters=tuple()):
    # print parameters
    self.paramValues = parameters
  
  def checkVersion(self, root):
    found = root.get('version')
    if self.VERSION is not None and self.VERSION != found:
      raise ConfigError, 'incompatible configuration file version: {} required but {} found'.format(self.VERSION, found)

  def parseParameters(self, root):
    ids = self._getParameterIDs(root.find('parameters'))
    if len(ids) > len(self.paramValues):
      raise ConfigError, 'too few parameters provided from the tool input: {} required, {} provided'.format(len(ids), len(self.paramValues))
    params = {}
    for i in range(len(ids)):
      params[ids[i]] = self.paramValues[i]
    return params

  def _getParameterIDs(self, paramel):
    ids = []
    if paramel is not None:
      for item in paramel.findall('parameter'):
        id = item.get('id') # a string ID of the parameter
        if id:
          ids.append(id)
    return ids
  
  def parseFile(self, file):
    try:
      root = eltree.parse(file).getroot()
      self.checkVersion(root)
    except IOError, mess:
      raise IOError, '{} configuration file {} not found or corrupt: {}'.format(self.FILE_PURPOSE, file, mess)
    except eltree.ParseError, mess:
      raise ConfigError, '{} configuration file {} corrupt: {}'.format(self.FILE_PURPOSE, file, mess)
    if root.tag == self.ROOT_TAG_NAME:
      return root
    else:
      raise ConfigError, '{} is not a {} configuration file'.format(file, self.FILE_PURPOSE)
    
  def _get(self, node, attr, default=NotImplemented):
    if node is None:
      if default is NotImplemented:
        raise ConfigError, 'required node not found'
      else:
        return default
    else:
      val = node.get(attr)
      if val is None:
        # if node exists, expect there was intent to specify the value, but in bad form
        param = node.get('parameter')
        if param: # parameterised (will be added from tool input)
          return self._parameter(param)
        else:
          raise ConfigError, '{} for {} node not found'.format(attr, node.tag)
      else:
        return val
  
  def _parameter(self, id):
    if id in self.parameters:
      return self.parameters[id]
    else:
      raise ConfigError, '{id} {purpose} parameter specified but not found in tool input'.format(id=id, purpose=self.FILE_PURPOSE)
  
  def typeGet(self, node, choiceDict, attr='type', default=NotImplemented):
    type = self._get(node, attr, default=default)
    try:
      return choiceDict[type]
    except KeyError:
      raise ConfigError, '{} is not a valid {} for {} node'.format(type, attr, node.tag)
  
  def boolGet(self, node, attr='true', default=NotImplemented):
    trueval = self._get(node, attr, default=default)
    try:
      return bool(int(trueval))
    except (TypeError, ValueError):
      raise ConfigError, '{} is not a valid boolean value for {} node'.format(trueval, node.tag)
  
  def valueGet(self, node, default=NotImplemented):
    valstr = self._get(node, 'value', default=default)
    try:
      return int(valstr)
    except (TypeError, ValueError):
      if valstr is None:
        return valstr
      else:
        raise ConfigError, '{} is not a valid value for {} node'.format(valstr, node.tag)
  
  def strGet(self, node, attr='id', default=NotImplemented):
    return self._get(node, attr, default=default)
  
  def nameGet(self, node, attr='name', default=NotImplemented):
    return self._get(node, attr, default=default)
  
  def ratioGet(self, node, default=NotImplemented):
    valstr = self._get(node, 'ratio', default=default)
    try:
      return float(valstr) / 100.0
    except (TypeError, ValueError):
      if valstr is None:
        return valstr
      else:
        raise ConfigError, '{} is not a valid ratio value for {} node'.format(valstr, node.tag)

        
def inferFieldTypes(data, slots, callers={}):
  types = {}
  for slot in slots:
    # common.debug(slot)
    caller = callers[slot] if slot in callers else operator.itemgetter(slot)
    # common.debug(caller)
    possible = []
    nonetype = type(None)
    for item in data:
      fldtype = type(caller(item))
      if fldtype is not nonetype:
        possible.append(fldtype)
        if len(possible) == 5:
          break
    # common.debug(possible)
    if possible:
      # print possible
      types[slot] = collections.Counter(possible).most_common(1)[0][0]
      # print types[slot]
    else:
      common.warning('could not infer type for {} slot (no values found), output may be impossible'.format(slot))
  return types