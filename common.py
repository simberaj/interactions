# COMMON.PY
# A common module for all scripts in the Interactions toolbox.
import sys, os, arcpy, operator, traceback, numpy, random


# constants defining neighbour table field names
NEIGH_FROM_FLD = 'ID_FROM'
NEIGH_TO_FLD = 'ID_TO'
# signals if debug messages are to be printed
debugMode = False

try:
  from debug import *
except ImportError:
  pass

# field type names for new fields
PY_TYPE_TO_OUT = {unicode : 'TEXT', str : 'TEXT', int : 'LONG', float : 'DOUBLE', numpy.float64 : 'DOUBLE'}
IN_TYPE_TO_PY = {'Integer' : int, 'Double' : float, 'String' : unicode, 'SmallInteger' : int, 'OID' : int}
PY_TYPE_TO_STR = {unicode : 'unicode', str : 'str', int : 'int', float : 'float', numpy.float64 : 'float'}
INT_FIELD_DESCRIBE = 'Integer'
NET_FIELDS = [('SourceID', 'SourceID', None), ('SourceOID', 'SourceOID', None), ('PosAlong', 'PosAlong', None), ('SideOfEdge', 'SideOfEdge', None)]
NET_FIELD_MAPPINGS = 'SourceID SourceID #;SourceOID SourceOID #;PosAlong PosAlong #;SideOfEdge SideOfEdge #'

DEFAULT_SPATIAL_EXT = 'shp' # nondatabase default file extension
DEFAULT_TABLE_EXT = 'dbf'
ORIGIN_MARKER = 'O_' # field markers for od attributes of interactions
DESTINATION_MARKER = 'D_'
SHAPE_KEY = 'SHAPE' # auxiliary key for shape information
SHAPE_TYPE = 'SHAPE'

def checkFile(file):
  if not arcpy.Exists(file):
    raise IOError, '%s does not exist' % file.decode('cp1250').encode('utf8')
  return file

def query(target, mssql, *args):
  '''Prepares a mssql query to target such that fields are properly quoted.'''
  main = (mssql % args)
  if '.mdb' in target: # is in personal geodatabase (square brackets used)
    return main
  else: # quotes used
    return main.replace('[', '"').replace(']', '"')

def inTypeToOut(inType):
  try:
    return PY_TYPE_TO_OUT[IN_TYPE_TO_PY[inType]]
  except KeyError:
    raise ValueError, 'field of unknown type: ' + str(inType)

def inTypeToPy(inType):
  try:
    return IN_TYPE_TO_PY[inType]
  except KeyError:
    raise ValueError, 'field of unknown type: ' + str(inType)

def pyTypeToOut(pyType):
  try:
    return PY_TYPE_TO_OUT[pyType]
  except KeyError:
    raise ValueError, 'field of unknown type: ' + str(pyType)
    
def fieldType(pythonType):
  '''Returns a string for the passed Python type that may be used in arcpy.AddField as field type.'''
  return pyTypeToOut(pythonType)

def describeToField(describe):
  return inTypeToOut(describe)

def typeOfField(layer, field):
  return outTypeOfField(layer, field)

def outTypeOfField(layer, field):
  return inTypeToOut(inTypeOfField(layer, field))

def pyTypeOfField(layer, field):
  return inTypeToPy(inTypeOfField(layer, field))

def inTypeOfField(layer, field):
  typeList = fieldTypeList(layer)
  if field in typeList:
    return typeList[field]
  else:
    fldNames = list(typeList.keys())
    for lyrFld in fldNames:
      typeList[lyrFld.upper()] = typeList[lyrFld]
    if field.upper() in typeList:
      return typeList[field.upper()]
    else:
      raise ValueError, u'field %s not found in %s' % (field, layer)

def pyStrOfType(pyType):
  try:
    return PY_TYPE_TO_STR[pyType]
  except KeyError:
    raise ValueError, 'field of unknown type: ' + str(pyType)

def addFields(layer, fields, strict=False):
  fieldList = fieldTypeList(layer)
  for name, fldType in fields:
    if name in fieldList:
      if strict:
        raise ValueError, 'field %s already exists' % name
      else:
        if inTypeToPy(fieldList[name]) == fldType:
          warning('field %s already exists' % name)
          continue
        else:
          warning('field %s already exists with different type %s: will be deleted' % (name, fieldList[name]))
          arcpy.DeleteField_management(layer, [name])
    arcpy.AddField_management(layer, name, pyTypeToOut(fldType))

def featurePath(location, file, ext=DEFAULT_SPATIAL_EXT):
  return addExt(os.path.join(location, file), ext)

def tablePath(location, file, ext=DEFAULT_TABLE_EXT):
  return addExt(os.path.join(location, file), ext)

def tableName(location, file, ext=DEFAULT_TABLE_EXT):
  if isInDatabase(location):
    return file
  else:
    return addTableExt(file, ext)

def addExt(path, ext=DEFAULT_SPATIAL_EXT):
  if not isInDatabase(path) and not hasExt(path):
    return path + '.' + ext
  else:
    return path

def addFeatureExt(path, ext=DEFAULT_SPATIAL_EXT):
  return addExt(path, ext)

def addTableExt(path, ext=DEFAULT_TABLE_EXT):
  return addExt(path, ext)

def hasExt(path):
  return path.rfind('.') > max(path.rfind('/'), path.rfind('\\'))
  
def parameters(number):
  '''Returns tool parameters from the tool input as strings.'''
  if len(sys.argv) == 1:
    sys.exit(1)
  params = []
  for i in range(number):
    params.append(arcpy.GetParameterAsText(i))
  return params

def setParameter(paramIndex, output):
  arcpy.SetParameterAsText(paramIndex, output)
  
def count(layer):
  '''Counts the number of features (rows) in the layer.'''
  return int(arcpy.GetCount_management(layer).getOutput(0))

def fieldTypeList(layer, type=None):
  '''Returns a dict of field names : types of the specified layer attributes.'''
  if type is None:
    flist = arcpy.ListFields(layer)
  else:
    flist = arcpy.ListFields(layer, '', type)
  fields = {}
  for field in flist:
    fields[field.name] = field.type
  return fields
    
def fieldList(layer, type=None):
  '''Returns a list of field names of the specified layer attributes.'''
  if type is None:
    return [field.name for field in arcpy.ListFields(layer)]
  else:
    return [field.name for field in arcpy.ListFields(layer, '', type)]

def parseFields(fieldList):
  '''Parses fields passed from the tool input.'''
  fields = fieldList.split(';')
  i = 0
  while i < len(fields):
    if fields[i] == '':
      fields.pop(i)
    else:
      fields[i] = fields[i].strip("'")
      i += 1
  return fields

def parseStats(stats):
  '''Parses statistics setup.'''
  return [item.split(' ') for item in stats.split(';')]

def statListToFields(statList):
  '''Converts a list of statistics setup to resulting field names.'''
  return [item[1] + '_' + item[0] for item in statList]
  
def isView(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType in (u'FeatureLayer', u'TableView'))
  
def isLayer(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType == u'FeatureLayer')

def isShapefile(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType == u'ShapeFile' or (desc.dataType == u'FeatureLayer' and desc.dataElement.dataType == u'ShapeFile'))

def isTableView(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType == u'TableView')

def isFeatureClass(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType in (u'FeatureClass', u'ShapeFile'))

def hasGeometry(layer):
  desc = arcpy.Describe(layer)
  print desc.dataType, desc.dataType, desc.dataType
  return (desc.dataType in (u'FeatureLayer', u'FeatureClass', u'ShapeFile'))
  
def toFeatureClass(layer):
  desc = arcpy.Describe(layer)
  if desc.dataType in (u'FeatureClass', u'ShapeFile'):
    return layer
  elif desc.dataType == u'FeatureLayer':
    return desc.dataElement.catalogPath
  else:
    raise ValueError, 'cannot convert %s (type %s) to feature class' % (layer, desc.dataType, desc.dataElementType)
  
def selection(source, target, query):
  if hasGeometry(source):
    arcpy.MakeFeatureLayer_management(source, target, query)
  else:
    arcpy.MakeTableView_management(source, target, query)
  
def select(source, target, query):
  if hasGeometry(source):
    arcpy.Select_analysis(source, target, query)
  else:
    arcpy.TableSelect_analysis(source, target, query)
  
def copy(source, target):
  if hasGeometry(source):
    arcpy.CopyFeatures_management(source, target)
  else:
    arcpy.CopyRows_management(source, target)
  
def multiplyDistance(dist, mult):
  distNum, distUnit = dist.split()
  return str(int(float(distNum) * mult)) + ' ' + distUnit
  
  
  
def getSource(layer):
  desc = arcpy.Describe(layer)
  return (desc.dataType == u'FeatureClass')  

def isInDatabase(location):
  '''Returns True if the location is inside a file or personal geodatabase, False otherwise.'''
  return ('.gdb' in location or'.mdb' in location)

def folder(location):
  '''Returns a system folder in which the specified file is located.'''
  while isInDatabase(location):
    location = os.path.dirname(location)
  return location

def location(path):
  if hasExt(path):
    while hasExt(path):
      path = os.path.dirname(path)
    return path
  else:
    if isFeatureClass(path):
      return os.path.dirname(path)
    else:
      return location(toFeatureClass(path))

def toInt(value, name):
  try:
    return int(str(value))
  except (ValueError, UnicodeEncodeError):
    raise ValueError, 'invalid ' + name + ' format: must be an integral number, got ' + str(value)

def toFloat(value, name):
  try:
    return float(str(value).replace(',', '.'))
  except (ValueError, UnicodeEncodeError):
    raise ValueError, 'invalid ' + name + ' format: must be a number, got ' + str(value)

def toBool(value, name):
  try:
    return bool(str(value).lower() == 'true' or str(value) == '1')
  except (ValueError, TypeError):
    raise ValueError, 'invalid ' + name + ' format: must be a number or "true" or "false", got ' + str(value)
    
def invertQuery(query):
  return '' if not query else ('NOT (' + query + ')')

def inBounds(val, min, max):
  if val < min: return min
  elif val > max: return max
  else: return val

def maxKey(dictionary):
  '''Returns a key from the dictionary that corresponds to the highest value.'''
  return max(dictionary.iteritems(), key=operator.itemgetter(1))[0]

def constantLambda(value):
  return (lambda whatever: value)

def sublayer(layer, subName):
  return arcpy.mapping.ListLayers(layer, subName)[0]

def getShapeType(layer):
  return arcpy.Describe(layer).shapeType.upper()
  
def recreate(layer, location, outName, transferFlds):
  outPath = addFeatureExt(arcpy.CreateFeatureclass_management(location, outName, getShapeType(layer), spatial_reference=layer).getOutput(0))
  fieldTypes = fieldTypeList(layer)
  for fld in transferFlds:
    arcpy.AddField_management(outPath, fld, inTypeToOut(fieldTypes[fld]))
  return outPath

def createTable(path, useDBF=True):
  location = os.path.dirname(path)
  name = os.path.basename(path)
  return arcpy.CreateTable_management(
    location, (addTableExt(name) if (useDBF and not isInDatabase(location)) else name)
  ).getOutput(0)

def createFeatureClass(path, shapeType=None, template=None, crs=None):
  if not (template or crs):
    raise ValueError, 'insufficient shape data for {} provided'.format(path)
  if shapeType is None and crs is not None:
    shapeType = getShapeType(crs)
  return addFeatureExt(arcpy.CreateFeatureclass_management(
    os.path.dirname(path), os.path.basename(path),
    geometry_type=shapeType, template=template, spatial_reference=crs).getOutput(0))

def overwrite(val=True):
  arcpy.env.overwriteOutput = val

def delete(*args):
  try:
    for item in args:
      arcpy.Delete_management(item)
  except:
    pass

def addField(layer, name, fldType):
  if isShapefile(layer):
    name = name[:10]
  arcpy.AddField_management(layer, name, pyTypeToOut(fldType))

  
class runtool:
  def __init__(self, parcount=0, debug=None, overwrite=True):
    if debug is not None:
      debugMode = debug
    arcpy.env.overwriteOutput = overwrite
    if parcount:
      self.params = parameters(parcount)

  def __getitem__(self, index):
    return self.params[index]
      
  def __enter__(self):
    return self.params
  
  def __exit__(self, exc_type, exc_value, tb):
    if exc_type is not None:
      if debugMode:
        debug('\n'.join(traceback.format_exception(exc_type, exc_value, tb)))
      else:
        arcpy.AddError(u'{} {}'.format(exc_type, exc_value))
        return True
    else:
      done()

  
class Messenger:
  def __init__(self, debugMode=False):
    pass
  
  def done(self):
    '''Signals ArcPy that the script has successfully terminated. If the script is running in a debug mode, raises an error to bring the tool dialog up again for debugger's convenience; otherwise just displays the message.'''
    done()
  
  def message(self, mess):
    '''Adds a simple message to the output log.'''
    message(mess)
  
  def progress(self, message):
    '''Signals tool progress by setting the progressor label. In debug mode, prints a message instead.'''
    progress(message)
  
  def progressor(self, message, count):
    return progressor(message, count)
  
  def debug(self, message):
    '''Displays a debug message (only in debug mode).'''
    debug(message)
  
  def warning(self, message):
    '''Displays a warning.'''
    warning(message)
  
  def error(self, message):
    '''Raises an error with the specified message using the ArcPy mechanism.'''
    error(message)
  
  def getDebugMode(self):
    return debugMode

class MutedMessenger(Messenger):
  def __init__(self):
    pass

  def message(self, message):
    pass
  
  def progress(self, message):
    pass
  
  def progressor(self, message, count):
    return MutedProgressBar()
  
class ProgressBar:
  '''ArcPy progress bar control class.'''

  def __init__(self, text, count):
    '''Initializes the progress bar going from 0 to 100 % with the text to display above it and the number of steps to be performed.'''
    self.text = text
    self.count = count
    self.progressBy = 100.0 / self.count
    self.posBy = int(self.progressBy) if int(self.progressBy) >= 1 else 1
    self.position = 0 # progressbar position
    self.posExact = 0 # exact position (noninteger)
    self.progress = 0 # how many of count has passed
    arcpy.SetProgressor('step', self.text, self.position, 100, self.posBy)
  
  def move(self):
    '''Signals the progress bar that one step has been performed. The progress bar may move forward if the step means at least one per cent difference.'''
    self.progress += 1
    self.posExact += self.progressBy
    if int(self.posExact) > self.position: # if crossed per cent to one more
      self.position = int(self.posExact)
      arcpy.SetProgressorPosition(self.position)
  
  def end(self):
    '''Ends the counting and resets the progressor.'''
    arcpy.ResetProgressor()

class MutedProgressBar(ProgressBar):
  def __init__(self, *args):
    pass
  
  def move(self):
    pass
    
  def end(self):
    pass
        
class MessagingClass:
  def __init__(self, messenger=Messenger(True)):
    self.messenger = messenger
  
  def done(self):
    self.messenger.done()

class PathManager:
  def __init__(self, outPath, delete=True):
    self.outPath = outPath
    self.location = os.path.dirname(self.outPath)
    self.outName = os.path.basename(self.outPath)
    self.tmpCount = -1
    self.delete = True
  
  def __enter__(self):
    self.tmpFiles = []
    self.tmpFields = {}
    random.seed(self.location)
    return self
  
  def tmpFile(self):
    tmp = self._tmpPath()
    self.tmpFiles.append(tmp)
    return tmp
  
  def tmpLayer(self):
    return self._tmpName()
  
  def tmpField(self, layer, fldType):
    name = self._tmpName().upper()
    arcpy.AddField_management(layer, name, pyTypeToOut(fldType))
    if layer not in self.tmpFields: self.tmpFields[layer] = []
    self.tmpFields[layer].append(name)
    return name
    
  def _tmpName(self):
    self.tmpCount += 1
    return 'tmp_{:02d}{:04d}'.format(self.tmpCount, int(1e4 * random.random()))
  
  def _tmpPath(self):
    return featurePath(self.location, self._tmpName())
  
  def __exit__(self, *args):
    if self.delete:
      progress('deleting temporary files')
      for file in self.tmpFiles:
        try:
          arcpy.Delete_management(file)
        except:
          pass
      progress('deleting temporary fields')
      for layer in self.tmpFields:
        try:
          arcpy.DeleteField_management(layer, self.tmpFields[layer])
        except:
          pass
  
  def getLocation(self):
    return self.location

  def getOutputName(self):
    return self.outName

    
def warning(text):
  '''Displays a warning to the tool user.'''
  arcpy.AddWarning((u'WARNING: ' if debugMode else u'') + encodeMessage(text))

def debug(*args):
  '''Displays a debug message (only in debug mode).'''
  if debugMode:
    arcpy.AddMessage(u'DEBUG: ' + ' '.join(encodeMessage(arg) for arg in args))

def progress(text):
  '''Signals tool progress by setting the progressor label.'''
  if debugMode:
    arcpy.AddMessage(u'PROGRESS: ' + encodeProgress(text))
  else:
    arcpy.SetProgressorLabel(encodeProgress(text))

def done():
  '''Signals ArcPy that the script has successfully terminated. If the script is running in a debug mode, raises an error to bring the tool dialog up again for debugger's convenience; otherwise just displays the message.'''
  if debugMode:
    arcpy.AddMessage('PROGRESS: Done.')
  # else:
  arcpy.SetProgressor('default', 'Done.')

def message(text):
  '''Signals an ordinary message to the user.'''
  arcpy.AddMessage(encodeMessage(text))

def encodeMessage(text):
  '''Encodes the message to UNICODE.'''
  try:
    if isinstance(text, unicode):
      return text
    elif isinstance(text, str):
      return unicode(text, encoding='utf8')
    else:
      return str(text)
  except (UnicodeEncodeError, UnicodeDecodeError):
    return 'unknown message'

def encodeProgress(text):
  return encodeMessage(text[:1].upper() + text[1:] + '...')
  
def progressor(text, count):
  progress(text)
  return ProgressBar(encodeProgress(text), count)

def getDebugMode():
  return debugMode