MAX_VALUE = 254 # arcgis seems to have problems with 255 (makes holes where one of RGB parts is 255)
BLACK_RGB = [0] * 3
WHITE_RGB = [MAX_VALUE] * 3

import operator

## COLORING and color objects
class ColorCodeError(Exception):
  '''An error signalling invalid color hex code input.'''
  pass

class ColorZone:
  '''A zone instance that can be colored.'''

  def __init__(self, id):
    self.id = id
    self.colN = 0 # number of colored neighbours
    self.neighColors = set()
    self.color = None
    self.neighs = []
  
  def addNeigh(self, neigh):
    self.neighs.append(neigh)
  
  def getColor(self):
    return self.color
  
  def colorWithFirst(self, colors, shuffle=True):
    '''Colors itself with the first color in the provided list that none of its neighbours has.
    If configured with shuffle property on, shuffles the list randomly before choosing.'''
    if shuffle:
      random.shuffle(colors)
    for col in colors:
      if col not in self.neighColors:
        self.colorWith(col)
        break
  
  def colorWith(self, color):
    '''Colors itself with the given color and notifies its neighbours of it.'''
    self.color = color
    for neigh in self.neighs:
      neigh.neighColored(color)
  
  def colorIfNot(self, color):
    '''If still uncolored, colors itself with the given color.'''
    if self.color is None:
      self.color = color
  
  def neighColored(self, color):
    '''Records that a neighbour has been colored with a given color.'''
    self.colN += 1
    self.neighColors.add(color)
  
  def getSorter(self):
    '''Returns the urgency with which it should be colored.
    The urgency increases with the number of neighbours colored and secondarily with the total number of neighbours.'''
    return self.colN + (len(self.neighs) - self.colN) * 1e-6
  
  
class ColorChooser:
  sortFx = operator.methodcaller('getSorter')
  WHITE = 'ffffff'

  def __init__(self, neighbourhood, colorFileName):
    self.zones = self.zonesFromNeighbourhood(neighbourhood)
    self.colors = self.loadColorList(colorFileName)

  def zonesFromNeighbourhood(self, neighDict):
    zones = {}
    # create ColorZone objects
    for id in neighDict:
      zones[id] = ColorZone(id)
    for idFrom in neighDict:
      for idTo in neighDict[idFrom]:
        zones[idFrom].addNeigh(zones[idTo])
    return zones
  
  def colorHeuristically(self, shuffle=True):
    '''Colors the given zones with colors from the given list so that no neighbouring zones have the same color.'''
    if shuffle:
      global random
      import random
    uncolored = list(self.zones.values())
    while uncolored:
      uncolored.sort(key=self.sortFx)
      now = uncolored.pop()
      now.colorWithFirst(self.colors, shuffle=shuffle)
    for zone in self.zones.itervalues():
      zone.colorIfNot(self.WHITE)
    return self.zones

  @staticmethod
  def loadColorList(fileName):
    colorList = []
    with open(fileName, 'r') as file:
      for line in file.readlines():
        col = line.strip().split('#')[0].strip()
        if col:
          colorList.append(col)
    return colorList

def rgbToHex(color):
  return ''.join('{:02x}'.format(int(num) if num < MAX_VALUE else MAX_VALUE) for num in color)

def hexToRGB(code):
  code = code.strip('#')
  try:
    return [int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)]
  except (ValueError, IndexError):
    raise ColorCodeError('invalid color code: ' + repr(code))
  
def rgbToHSV(rgb):
  maxcomp = max(rgb)
  mincomp = min(rgb)
  chroma = float(maxcomp - mincomp)
  if chroma == 0:
    return [0, 0, maxcomp]
  else:
    if rgb[0] == maxcomp: pseudohue = ((rgb[1] - rgb[2]) / chroma) % 6
    if rgb[1] == maxcomp: pseudohue = ((rgb[2] - rgb[0]) / chroma) + 2
    if rgb[2] == maxcomp: pseudohue = ((rgb[0] - rgb[1]) / chroma) + 4
    return [pseudohue * MAX_VALUE / 6, chroma / maxcomp * MAX_VALUE, maxcomp]

def hsvToRGB(hsv):
  chroma = hsv[1] * float(hsv[2]) / MAX_VALUE
  pseudohue = hsv[0] * 6.0 / MAX_VALUE
  pseudohueint = int(pseudohue % 6)
  seclargest = chroma * (1 - abs(pseudohue % 2 - 1))
  smallest = hsv[2] - chroma
  lowgray = [smallest] * 3
  lowgray[{0 : 0, 1 : 1, 2 : 1, 3 : 2, 4 : 2, 5 : 0}[pseudohueint]] += chroma
  lowgray[{0 : 1, 1 : 0, 2 : 2, 3 : 1, 4 : 0, 5 : 2}[pseudohueint]] += seclargest
  return lowgray

# def rgbToHSL(rgb):
  # maxcomp = max(rgb)
  # mincomp = min(rgb)
  # chroma = float(maxcomp - mincomp)
  # if chroma == 0:
    # return createColor(0, 0, maxcomp)
  # else:
    # if rgb[0] == maxcomp: pseudohue = ((rgb[1] - rgb[2]) / chroma) % 6
    # if rgb[1] == maxcomp: pseudohue = ((rgb[2] - rgb[0]) / chroma) + 2
    # if rgb[2] == maxcomp: pseudohue = ((rgb[0] - rgb[1]) / chroma) + 4
    # light = (mincomp + maxcomp) / 510.0 # 2 * 255
    # satur = chroma / (1 - abs(2 * light - 1))
    # return createColor(pseudohue * 255 / 6, satur, light * 255)

# def hslToRGB(hsv):
  # pseudohue = int(hsv[0] * 6.0 / 255)
  # chroma = hsv[1] * (1 - abs(2 * hsv[2] - 1))
  # seclargest = chroma * (1 - abs(pseudohue % 2 - 1))
  # smallest = hsv[2] - chroma / 2.0
  # print chroma, pseudohue, seclargest, smallest
  # lowgray = createColor(smallest, smallest, smallest)
  # if hsv[0] == 0 and seclargest == 0:
    # return lowgray
  # print lowgray
  # lowgray[{0 : 0, 1 : 1, 2 : 1, 3 : 2, 4 : 2, 5 : 0}[pseudohue]] += hsv[1]
  # print lowgray
  # lowgray[{0 : 1, 1 : 0, 2 : 2, 3 : 1, 4 : 0, 5 : 2}[pseudohue]] += seclargest
  # print lowgray
  # return lowgray

# def mixHSL(hsvitems):
  # value = sum(x[1] for x in hsvitems)
  # if value > 1:
    # raise ValueError, 'cannot mix over 1'
  # hsvitems.sort(key=(lambda x: x[1]))
  # return createColor(value * 255)
  # for col, deg in hsvitems:
    # init[0] += col[0] * deg # / value
    # init[1] += col[1] * deg
    # init[2] += col[2] * deg
  # return init

def mixDirect(rgbitems):
  value = sum(x[1] for x in rgbitems)
  if (value - 1) > 1e-5:
    raise ValueError, 'cannot mix over 1, got %f from %s' % (value, rgbitems)
  result = [0, 0, 0]
  for item in rgbitems:
    for i in range(3):
      result[i] += item[0][i] * item[1]
  return result

def invert(color):
  return [MAX_VALUE - item for item in color]

def mixInverted(rgbitems):
  return invert(mixDirect([(invert(item[0]), item[1]) for item in rgbitems]))

# import common
MIN_MIXHUE_GRAYLEVEL = 0.25
MIN_MIXHUE_VALUE = MIN_MIXHUE_GRAYLEVEL * MAX_VALUE
  
def mixHue(hue, degrees):
  # common.debug(hue)
  # common.debug(degrees)
  sumdeg = sum(degrees)
  # common.debug(sumdeg)
  if (sumdeg - 1) > 1e-5:
    raise ValueError, 'cannot mix over 1, got %g from %s' % (sumdeg, degrees)
  maxdeg = max(degrees)
  if maxdeg < 1e-5:
    return [MIN_MIXHUE_VALUE] * 3 
  else:
    superiority = maxdeg / sumdeg
    value = MIN_MIXHUE_GRAYLEVEL + (1 - MIN_MIXHUE_GRAYLEVEL) * sumdeg
    # superiority = (2 * maxdeg - value) / maxdeg
    # common.debug([hue, superiority * MAX_VALUE, value * MAX_VALUE])
    return [hue, superiority * MAX_VALUE, value * MAX_VALUE]
  
def mixAvgHue(rgbitems):
  if rgbitems:
    return hsvToRGB(mixHue(rgbToHSV(mixDirect(rgbitems))[0], [x[1] for x in rgbitems]))
  else:
    return [0, 0, 0]

def mixMaxHue(rgbitems):
  if rgbitems:
    maxitem = max(rgbitems, key=(lambda x: x[1]))
    return hsvToRGB(mixHue(rgbToHSV(maxitem[0])[0], [x[1] for x in rgbitems]))
  else:
    return [0, 0, 0]

def mixHSVMax(hsvitems):
  if hsvitems:
    maxitem = max(hsvitems, key=(lambda x: x[1]))
    return mixHue(maxitem[0][0], [x[1] for x in hsvitems])
  else:
    return [0, 0, 0]
  # for col, deg in hsvdict.iteritems():
    # init[0] += col[0] * deg / value
    # init[1] += col[1] * deg
    # init[2] += col[2] * deg
  # return init

COLOR_MIXERS = {'additive' : mixDirect, 'subtractive' : mixInverted, 'maxhue' : mixMaxHue, 'avghue' : mixAvgHue}
  
if __name__ == '__main__':
  import sys
  toHSV = bool(len(sys.argv) > 1 and sys.argv[1] == 'rgb')
  inp = raw_input().strip()
  while inp:
    rgbcol = [int(item) for item in inp.split()]
    print ' '.join([str(x) for x in (rgbToHSV(rgbcol) if toHSV else hsvToRGB(rgbcol))])
    inp = raw_input().strip()
  # reg1col = rgbToHSV([MAX_VALUE, 0, 0])
  # reg2col = rgbToHSV([0, 0, MAX_VALUE])
  # print reg1col, reg2col
  # deg1 = int(sys.argv[1]) / float(int(sys.argv[1]) + int(sys.argv[3]) + int(sys.argv[4]))
  # deg2 = int(sys.argv[3]) / float(int(sys.argv[1]) + int(sys.argv[2]) + int(sys.argv[3]))
  # print deg1, deg2
  # col = mixHSVMax([(reg1col, deg1), (reg2col, deg2)])
  # print col
  # print hsvToRGB(col)
  # col = mixAvgHue([(reg1col, deg1), (reg2col, deg2)])
  # print col
  # print rgbToHSV(col)
  