import sys, arcpy, operator, numpy
from collections import defaultdict, deque
sys.path.append('.')
import common, colors

MASS_TO_STRG = 1e-10
ID_SORTER = operator.methodcaller('getID')
MASS_SORTER = operator.methodcaller('getMass')
SECONDARY_MASS_SORTER = operator.methodcaller('getSecondaryMass')
GAIN_SORTER = operator.methodcaller('getGain')

class BaseInteractions(defaultdict):
  '''An "abstract" base class that stores interaction targets and strengths.
  
  A sibling of collections.defaultdict(int) storing pairs target : strength, where target should be RegionalUnit and strength either a numeric value or an InteractionVector.
  
  Provides basic vector arithmetic methods (i. e. addition of two instances results in one with strengths to identical targets summed).
  
  May contain a "raw" attribute that corresponds to strengths of interactions to undefined targets.
  
  Caches a sum of all its values.'''

  def __init__(self, factory, *args, **kwargs):
    defaultdict.__init__(self, factory, *args, **kwargs)
    self.raw = factory()
    self._sum = 0
    self._summed = False

  def __add__(self, plusinter):
    new = self.copy()
    new += plusinter
    return new
  
  def __mul__(self, factor):
    new = self.new()
    for zone in self:
      new[zone] = self[zone] * factor
    new.raw += self.raw * factor
    self._summed = False
    return new
  
  def __iadd__(self, inter):
    for zone in inter:
      self[zone] += inter[zone]
    self.raw += inter.raw
    self._summed = False
    return self
  
  def __isub__(self, inter):
    for zone in inter:
      self[zone] -= inter[zone]
    self.raw -= inter.raw
    self._summed = False
    return self

  def __div__(self, divisor):
    new = self.new()
    divisor = float(divisor)
    for target in self:
      new[target] = self[target] / divisor
    new.raw += self.raw / divisor
    return new
    
  @classmethod
  def new(cls):
    return cls()
  
  def copy(self):
    cp = self.new()
    for target in self:
      cp[target] = self[target]
    cp.raw = self.raw
    return cp
  
  def restrict(self, restricted):
    '''Removes all targets that are not contained in restricted from the interactions.'''
    todel = []
    for target in self:
      if target not in restricted:
        todel.append(target) # to prevent RuntimeError from changing dict size during iteration
        self._summed = False
    for target in todel:
      del self[target]
    return self
  
  def restrictToRegions(self):
    '''Removes all targets that are not regions from the interactions.'''
    todel = []
    for target in self:
      if not isinstance(target, Region):
        todel.append(target)
    for target in todel:
      del self[target]
    self._summed = False
    return self
  
  def exclude(self, excluded):
    '''Removes all targets that are contained in EXCLUDED from the interactions.'''
    for exc in excluded:
      if exc in self:
        del self[exc]
        self._summed = False
    return self
  
  def onlyClassSum(self, targetClass):
    '''Returns its copy with only flows targetting the specified class retained.'''
    total = self.default_factory()
    for target in self:
      if isinstance(target, targetClass):
        total += self[target]
    return total

  @classmethod
  def inflowsTo(cls, sources):
    '''Given a list of RegionalUnits, returns a sum of their inflows.'''
    # if len(sources) == 1: return sources[0].getInflows()
    flows = cls.new()
    for zone in sources:
      flows += zone.getInflows()
    return flows

  @classmethod
  def outflowsFrom(cls, sources):
    '''Given a list of RegionalUnits, returns a sum of their outflows.'''
    # common.debug(sources)
    # common.debug([(x, x.getOutflows()) for x in sources])
    # if len(sources) == 1: return sources[0].getOutflows()
    flows = cls.new()
    for zone in sources:
      flows += zone.getOutflows()
    return flows
  
  def sum(self):
    '''Returns a sum of its values (strengths) including raw.'''
    if not self._summed:
      # print self
      # print sum(self.itervalues()), self.default_factory(), self.raw
      self._sum = (sum(self.itervalues()) if len(self) > 0 else self.default_factory()) + self.raw
      self._summed = True
      # print self._sum, len(self), sum(self.itervalues()), self.default_factory(), self.raw, self.default_factory() + self.raw
    return self._sum
  
  def toCore(self):
    '''Returns its copy. If any of its targets is a zone that is a core of a region, its value is added to that region's value instead.'''
    regional = self.new()
    for target in self:
      if isinstance(target, Region):
        region = target
      else:
        region = target.getCore()
      if region is None:
        regional[target] += self[target]
      else:
        regional[region] += self[target]
    regional.raw = self.raw
    return regional
  
  def toRegional(self):
    '''Returns its copy. If any of its targets is a zone that is inside a region, its value is added to that region's value instead.'''
    regional = self.new()
    for target in self:
      if isinstance(target, Region):
        region = target
      else:
        region = target.getRegion()
      if region is None:
        regional[target] += self[target]
      else:
        regional[region] += self[target]
    regional.raw = self.raw
    return regional

  def sumToCoreOf(self, region):
    '''Returns a sum of strengths to all its targets that are zones of a specified region's core.'''
    total = self.default_factory()
    for target, strength in self.iteritems():
      if target.isCoreOf(region):
        total += strength
    return total
  
  def sumToRegion(self, region):
    '''Returns a sum of strengths to all its targets that are zones of a specified region.'''
    total = self.default_factory()
    for target, strength in self.iteritems():
      if target.isInRegion(region):
        total += strength
    return total
  
  def sumOutOf(self, region):
    '''Returns a sum of strengths to all its targets that are zones outside the specified region.'''
    total = self.default_factory()
    for target, strength in self.iteritems():
      if not target.isInRegion(region):
        total += strength
    return total
  
  def sumsByCore(self, region):
    '''Returns results of sumToCoreOf(region) and sumOutOf(region) in a two-member tuple. Should be a little faster.'''
    inside = self.default_factory()
    outside = self.default_factory()
    for target, strength in self.iteritems():
      if target.isCoreOf(region):
        inside += strength
      elif not target.isInRegion(region):
        outside += strength
    return (inside, outside)

  def sumsByRegion(self, region):
    '''Returns results of sumToRegion(region) and sumOutOf(region) in a two-member tuple. Should be a little faster.'''
    inside = self.default_factory()
    outside = self.default_factory()
    for target, strength in self.iteritems():
      if target.isInRegion(region):
        inside += strength
      else:
        outside += strength
    return (inside, outside)

  def addRaw(self, toAdd):
    '''Adds to raw interaction value (with unspecified targets).'''
    # common.debug(repr(toAdd))
    self.raw += toAdd
  
  def subRaw(self, toSub):
    '''Subtracts from raw interaction value (with unspecified targets).'''
    self.raw -= toSub
  
  def getRaw(self):
    '''Returns a raw interaction value (with unspecified targets).'''
    return self.raw

class Interactions(BaseInteractions):
  '''Simple interactions containing only a single strength value (int or float).'''

  def __init__(self, *args, **kwargs):
    BaseInteractions.__init__(self, int, *args, **kwargs)
    self.raw = 0
        
  def allOver(self, strength, exclude=[]):
    '''Returns all its interactions that have strength exceeding the given value and their target (or its region) is not contained in the exclude list.'''
    over = self.new()
    for target in self:
      if self[target] >= strength and (not exclude or (target not in exclude and target.getRegion() not in exclude)):
        over[target] = self[target]
    return over
  
  def max(self):
    '''Returns a maximum of its values.'''
    return max(self.itervalues()) if self else 0
    
  def strongest(self):
    '''Returns a target with the highest corresponding strength.'''
    return common.maxKey(self)
  
  def significant(self):
    '''Returns only significant flows according to Van Nuffel's algorithm.

    Compares the flows' strengths normalised by the largest one to the theoretical sequence of [1 / n] * n + [0] * (len(self) - n) for n starting at 1 and increasing as long as the correlation keeps growing. When it no longer grows, stops and declares the first n largest flows as significant.'''
    if not self: return self
    maxFlow = self.max()
    real = [(target, strength / maxFlow) for target, strength in self.iteritems()]
    real.sort(key=operator.itemgetter(1), reverse=True)
    expected = [0] * len(real) # expected flows: first num is 1/num, others are 0
    num = 0
    prevResVar = len(real) + 2
    resVar = prevResVar - 1
    while resVar < prevResVar: # as long as the residual variance keeps diminishing
      if num == len(real): break
      num += 1
      factor = 1 / float(num)
      for i in range(num):
        expected[i] = factor # first n expected values
      prevResVar = resVar
      # calculate the determination coefficient (only residual variance; the only thing needed to compare)
      resVar = 0
      for i in range(len(real)):
        resVar += (real[i][1] - expected[i]) ** 2
    # create the significant flows instance
    over = self.new()
    for item in real[:num]:
      over[item[0]] = item[1]
    return over
  
  def sortedTargets(self):
    '''Returns a list of its targets sorted by their corresponding interaction strengths descending (strongest interaction target first).'''
    return sorted(self, key=self.get, reverse=True)
  
  def orders(self):
    valords = sorted(self.itervalues(), reverse=True)
    ords = self.new()
    for target, val in self.iteritems():
      ords[target] = valords.index(val)
    return ords
  
  def relativeStrengths(self):
    maxFlow = self.max()
    if not maxFlow: maxFlow = 1
    return self / float(maxFlow)

  @staticmethod
  def transform(inter, callerName):
    caller = operator.methodcaller(callerName)
    trans = {}
    for item, rels in inter.iteritems():
      trans[item] = (caller(rels[0]), caller(rels[1]))
    return trans
        
    
class InteractionVector(list):
  '''A vector that stores values of MultiInteractions strengths.
  
  A sibling of list that adds a few methods to implement vector arithmetic.
  Overrides boolean checking - evaluates to True iff any of its items is nonzero.'''

  @classmethod
  def zero(cls, length):
    return cls([0] * length)
  
  def __add__(self, other):
    both = self.zero(len(self))
    both += self
    both += other
    return both
  
  def __iadd__(self, other):
    for i in range(len(self)):
      self[i] += other[i]
    return self
  
  def __mul__(self, factor):
    fac = self.new()
    for item in self:
      fac.append(item * factor)
    return fac
  
  def __isub__(self, other):
    for i in range(len(self)):
      self[i] -= other[i]
    return self
   
  def __div__(self, divisor):
    fac = self.new()
    divisor = float(divisor)
    for item in self:
      fac.append(item / divisor)
    return fac

  def __nonzero__(self):
    return bool(sum(self))
  
  def __repr__(self):
    return 'InteractionVector' + list.__repr__(self)
   
  @classmethod
  def new(cls):
    return cls()

class MultiInteractions(BaseInteractions):
  '''Interactions with more than one strength. Using InteractionVector to store their values.'''
  
  defaultLength = None
  
  def __init__(self, length=None, *args, **kwargs):
    if length is None:
      if self.defaultLength is None:
        raise ValueError, 'must provide length for multiinteractions'
      else:
        length = self.defaultLength
    lamb = lambda: numpy.zeros(length)
    BaseInteractions.__init__(self, lamb, *args, **kwargs)
    
  @classmethod
  def setDefaultLength(cls, length):
    cls.defaultLength = length

  
class RegionalUnit:
  '''A measurable regional unit - a pseudoabstract superclass of Zone and Region allowing both of them to provide IDs.'''
  id = None

  def __init__(self, id):
    self.id = id

  def getID(self):
    return self.id

  # for interaction calculations (excluding zones by their region)
  def getRegion(self):
    return None
    
class Neighbour:
  '''A simple superclass allowing neighbourhood formalization.'''
  def __init__(self):
    self.neighbours = set()
  
  def addNeighbour(self, zone):
    self.neighbours.add(zone)
  
  def hasNeighbour(self, zone):
    return (zone in self.neighbours)
  
  def setNeighbours(self, neighs):
    if neighs:
      self.neighbours.update(neighs)
  
  def getNeighbours(self):
    return self.neighbours

class GeometricalZone(Neighbour):
  '''A zone that implements neighbourhood by geometry intersection.'''

  def __init__(self, id, geometry=None):
    self.id = id
    if geometry is not None:
      geometry = self.prepareGeometry(geometry)
    self.geometry = geometry
  
  def intersects(self, zone):
    # tried to test minimum bounding rectangles... no speedup obvious (probably is done already)
    return not self.geometry.disjoint(zone.getGeometry())
  
  def getGeometry(self):
    return self.geometry

  def getID(self):
    return self.id
  
  # copies geometry... the uncopied one didn't seem to work
  @staticmethod
  def prepareGeometry(polygon):
    array = arcpy.Array()
    for part in polygon:
      array.add(part)
    return arcpy.Polygon(array)


# zone (a basic territorial unit for which data is provided, usually a settlement)    
class RegionalZone(RegionalUnit, Neighbour):
  delegation = 'region'
  coreable = True

  def __init__(self, id, mass=None, unitID=None):
    '''Initialize the zone with a given ID and mass.'''
    RegionalUnit.__init__(self, id)
    Neighbour.__init__(self)
    self.mass = mass
    self.assignment = None
    self.removeAssignment()

  def getMass(self):
    return self.mass
  
  def getRawMass(self):
    return self.mass

  def addAssignment(self, ass):
    self.assignment = ass
    self._region = ass.getRegion()

  def removeAssignment(self, ass=None):
    if ass is None or ass is self.assignment:
      self.assignment = None
      self._region = None

  def getAssignments(self):
    return [self.assignment] if self.assignment is not None else []
  
  def getAssignmentTo(self, region):
    if self._region is region:
      return self.assignment
    else:
      return None
  
  def deassign(self):
    if self._region is not None:
      self.assignment.erase()

  def getRegion(self):
    '''Returns its region if it is in one, None otherwise.'''
    return self._region
    
  def getRegionID(self):
    if self._region is None:
      return None
    else:
      return self._region.getID()

  def getRegions(self):
    return [self._region] if self._region is not None else []
  
  def isInRegion(self, region):
    return self._region is region
        
  def isAssigned(self):
    return self._region is not None

  def getContiguousRegions(self):
    # oscillation assignments are included...
    contig = set()
    for zone in self.neighbours:
      contig.add(zone.getRegion())
    contig.discard(None)
    return contig
        
  def hasContiguousRegion(self, region):
    for zone in self.neighbours:
      if region is zone.getRegion():
        return True
    return False

  def isInContiguousRegion(self, region):
    return self._region is region and not self.assignment.isExclave()
      
  def __repr__(self):
    return '<Zone %s (%i)>' % (self.getID(), self.getMass())
  
  def transferExclaveFlag(self):
    pass
    
class NoFlowZone(RegionalZone):
  def __init__(self, id, mass, mass2=0, rigidUnitID=None, flexUnitID=None, location=None):
    '''Initialize the zone with a given ID and masses. Stores the administrative unit IDs to be able to be assigned to units created later.'''
    RegionalZone.__init__(self, id, mass)
    self.secondaryMass = mass2
    self.rigidUnitID = rigidUnitID
    self.flexUnitID = flexUnitID
    self.location = location
    
  def getRigidUnitID(self):
    return self.rigidUnitID
  
  def getFlexibleUnitID(self):
    return self.flexUnitID
  
  def setRigidUnit(self, unit):
    self.rigidUnit = unit

  def getRigidUnit(self):
    return self.rigidUnit

  def setFlexibleUnit(self, unit):
    self.flexibleUnit = unit

  def getFlexibleUnit(self):
    return self.flexibleUnit
  
  def getSecondaryMass(self):
    return self.secondaryMass
  
  def setLocation(self, loc):
    self.location = loc
  
  def getLocation(self):
    return self.location

  
class FlowZone(RegionalZone):
  delegation = 'region'
  penalization = 1
  interactionClass = Interactions
  coreable = True

  def __init__(self, id, mass=None, coop=None, assign=None, color=None, coreable=True):
    '''Initialize the zone with a given ID, mass, color and regional setup.
    
    coop signals that the zone should be merged to that region as a core,
    assign signals that the zone should be added to that region's hinterland.'''
    RegionalZone.__init__(self, id, (0 if mass is None else mass))
    self.inflows = self.interactionClass()
    self.outflows = self.interactionClass()
    self.mutualFlows = self.interactionClass()
    self.regionPreset = assign
    self.coop = coop
    self.coreable = coreable
    self.color = colors.hexToRGB(color) if color is not None and color.strip() else colors.WHITE_RGB
    self.exclaveFlag = 0
  
  def addInflow(self, source, strength):
    self.inflows[source] += strength
    self.mutualFlows[source] += strength
  
  def addOutflow(self, target, strength):
    self.outflows[target] += strength
    self.mutualFlows[target] += strength
  
  def addRawInflow(self, strength):
    self.inflows.addRaw(strength)
    self.mutualFlows.addRaw(strength)
  
  def addRawOutflow(self, strength):
    self.outflows.addRaw(strength)
    self.mutualFlows.addRaw(strength)
  
  def setInflows(self, inflows):
    self.inflows = inflows
    self.mutualFlows = self.inflows + self.outflows
  
  def setOutflows(self, outflows):
    self.outflows = outflows
    self.mutualFlows = self.inflows + self.outflows
  
  def getOutflow(self, target):
    return self.outflows[target]

  def sortOutflows(self):
    self.sortedTargets = self.outflows.sortedTargets()
  
  def relativizeOutflows(self):
    '''Changes its outflow values to the multiples of its largest flow.'''
    maxFlow = self.outflows.max()
    if not maxFlow: maxFlow = 1
    self.relativizedOutflows = self.outflows / float(maxFlow)
  
  def getRegionPreset(self):
    return self.regionPreset
    
  def getCoop(self):
    return self.coop
  
  def setColor(self, color):
    self.color = color
  
  def getColor(self):
    return self.color
  
  def getColorHex(self):
    return colors.rgbToHex(self.color)
  
  # deprecated, do not use
  def calcFuzzyColor(self, memName=None):
    '''Calculates a membership color using the provided membership function.'''
    if memFunc:
      self.color = self.membershipColor(self.membershipFlows(memName))
    else:
      reg = self.getRegion()
      if reg:
        self.color = reg.getColor()
      else:
        self.color = RGBColor.makeWhite()
  
  def getMaxOutflowTarget(self):
    tgt = common.maxKey(self.outflows)
    return tgt, self.outflows[tgt] / self.outflows.sum()
  
  def getOutflowIndex(self, target):
    return self.sortedOutflows.index(target)
  
  def getRelativeOutflow(self, target):
    return self.relativizedOutflows[target]
  
  def getRawOutflowPercent(self):
    return self.relativizedOutflows.getRaw()
  
  def getInflows(self):
    return self.inflows
    
  def getOutflows(self):
    return self.outflows
  
  def getMutualFlows(self):
    return self.inflows + self.outflows
  
  def getExclaveFlag(self):
    return self.exclaveFlag

  def transferExclaveFlag(self):
    '''Freezes the zone's current exclave status to the exclaveFlag variable.'''
    self.exclaveFlag = (1 if self.isExclave() else 0)
  
  def hamplMembership(self, region, penal=1):
    '''Returns Hampl membership function value for the given region.'''
    try:
      if self.isCoreOf(region): # core cannot be exclave
        iR, dR = self.mutualFlows.sumsByRegion(region)
        penal = 1
      else:
        iR, dR = self.mutualFlows.sumsByCore(region)
      # if self.id == '544256': common.debug((region, iR, dR))
      return penal * iR / float(iR + dR)
    except ZeroDivisionError:
      return 0
        
  def membershipMass(self, memName, region, penal=1):
    '''Returns the fraction of its mass contributed to its region via its specified membership function.'''
    return self.mass * getattr(self, memName)(region, penal=penal)
  
  def hamplMembershipMass(self, region, penal=1):
    return self.membershipMass('hamplMembership', region, penal=penal)
  
  def membershipFlows(self, memName, core=True, excl=False):
    '''Returns membership function values of the zone in all the regions it has any binding to.'''
    srcFlows = self.mutualFlows.toCore() if core else self.mutualFlows.toRegional()
    memFlows = self.interactionClass()
    excl = excl and bool(self.penalization != 1)
    if excl: regs = self.getContiguousRegions()
    for target in srcFlows:
      if isinstance(target, Region):
        memFlows[target] = getattr(self, memName)(target, penal=(self.penalization if excl and target not in regs else 1))
    return memFlows
  
  def getLesserCoreID(self):
    '''Returns its region ID if it is its core but the IDs are unequal.'''
    core = self.getCore()
    if core and core.getID() != self.id:
      return core.getID()
    else:
      return None
    
  # @staticmethod
  # def membershipColor(memberFlows):
    # '''Returns a membership color.
    # The color is computed as the average of the colors of the regions the zone has any binding to, weighted by the membership function in that region.'''
    # myColor = RGBColor()
    # sumdeg = 0.0
    # for reg in memberFlows:
      # myColor += reg.getColor() * memberFlows[reg]
      # sumdeg += memberFlows[reg]
    # rest = (1.0 - sumdeg) # fill up to 1 with white - should not be necessary
    # if abs(rest) > 0.001: # TODO: warn if using
      # myColor += RGBColor.makeWhite() * rest
    # return myColor
  
  def maxMembership(self, memFunc):
    regOutflows = self.mutualFlows.toCore()
    myReg = self.getCore()
    if myReg:
      regOutflows[myReg] = self.outflows.sumToRegion(myReg)
    for target, flow in sorted(regOutflows.items(), key=operator.itemgetter(1), reverse=True):
      if isinstance(target, Region):
        return memFunc(target, flow, self.getPenalizationDiff(target))
    return 0
    
  def sumFlows(self, out=True):
    return self.outflows.sum() if out else self.inflows.sum()
  
  def getPenalization(self, isExclave=None):
    if isExclave is None: isExclave = self.isExclave()
    return (self.penalization if isExclave else 1)
  
  def getPenalizationDiff(self, region):
    if self.penalization == 1:
      return 1 # no need to check anything, does not matter
    else:
      return self.getPenalization(not self.hasContiguousRegion(region))
  
  @classmethod
  def setExclavePenalization(cls, penal):
    cls.penalization = penal
  

class MonoZone(FlowZone):
  oscillationRatio = 1
  
  def __init__(self, *args, **kwargs):
    FlowZone.__init__(self, *args, **kwargs)
    self.removeAssignment()

  def isExclave(self): # if the zone is an exclave
    if self.assignment is not None:
      return self.assignment.isExclave()
    else:
      return False
  
  def addAssignment(self, ass):
    FlowZone.addAssignment(self, ass)
    self._iscore = ass.isCore()
  
  def removeAssignment(self, ass=None):
    FlowZone.removeAssignment(self, ass)
    if ass is None or ass is self.assignment:
      self._iscore = False
  
  def setAssignmentExclave(self, region=None):
    if self._region is not None:
      self.assignment.setExclave(True)
  
  def isCoreOf(self, region):
    return self._iscore and self._region is region
  
  def isInRegion(self, region):
    return self._region is region
        
  def getCore(self):
    '''Returns its region if it is its core, None otherwise.'''
    return self._region if self._iscore else None
    
  def getRegionColor(self):
    '''Transfers the color of the zone's region to the zone.'''
    if self._region is None:
      return colors.BLACK_RGB
    else:
      return self._region.getColor()
  

class MultiZone(FlowZone):
  def __init__(self, *args, **kwargs):
    RegionalZone.__init__(self, *args, **kwargs)
    self.assignments = []

  def isExclave(self): # if the zone is an exclave
    for ass in self.assignments:
      if not ass.isExclave():
        return False
    return True

  def addAssignment(self, ass):
    # common.debug('adding %s' % ass)
    self.assignments.append(ass)
  
  def removeAssignment(self, ass=None):
    # common.debug('removing %s' % ass)
    if ass in self.assignments:
      self.assignments.remove(ass)
      if len(self.assignments) == 1 and not self.assignments[0]:
        self.assignments[0].setDegree(1) # solidify the remaining assignment from 0 to 1
    else:
      pass
  
  def getAssignments(self):
    return self.assignments
    
  def getAssignmentTo(self, region):
    for ass in self.assignments:
      if ass.getRegion() == region:
        return ass
    return None
  
  def deassign(self):
    for ass in self.assignments:
      ass.erase()

  def setAssignmentExclave(self, region):
    for ass in self.assignments:
      if ass.getRegion() is region:
        ass.setExclave(True)
  
  def isCoreOf(self, region):
    for ass in self.assignments:
      if ass.getRegion() is region and ass.isCore():
        return True
    return False
  
  def isInRegion(self, region):
    for ass in self.assignments:
      if ass.getRegion() is region:
        return True
    return False
  
  def isInContiguousRegion(self, region):
    for ass in self.assignments:
      if ass.getRegion() is region and not ass.isExclave():
        return True
    return False
  
  def getRegion(self):
    '''Returns its region if it is in one, None otherwise.'''
    if not self.assignments:
      return None
    elif len(self.assignments) == 1:
      return self.assignments[0].getRegion()
    else:
      maxAss = max(self.assignments)
      if maxAss:
        return maxAss.getRegion()
      else:
        return None
      
  def getCore(self):
    '''Returns its region if it is its core, None otherwise.'''
    if self.assignments:
      if len(self.assignments) == 1:
        if self.assignments[0].isCore():
          return self.assignments[0].getRegion()
        else:
          return None
      else:
        # common.warning('multiassign: %s' % self.assignments) # TODO
        coreAss = [ass for ass in self.assignments if ass.isCore()]
        if coreAss:
          return max(coreAss).getRegion() # no nonzero check; core assignments never oscillate
        else:
          return None
    return None
    
  def getRegions(self):
    return [ass.getRegion() for ass in self.assignments]
  
  def isAssigned(self):
    return bool(self.assignments)

  def getRegionColor(self):
    '''Transfers the color of the zone's region to the zone.'''
    regs = self.getRegions()
    if len(regs) == 1:
      return regs[0].getColor()
    elif regs:
      return colors.WHITE_RGB
    else:
      return colors.BLACK_RGB
    

class SimpleAssignment:
  '''An assignment of a zone to a region.'''
  
  def __init__(self, zone, region):
    self.zone = zone
    self.region = region
    
  def tangle(self): # binds the relationship to both sides
    # common.debug('assigning %s to %s' % (self.zone, self.region))
    self.zone.addAssignment(self)
    self.region.addAssignment(self)
    
  def erase(self): # erases the relationship from both sides
    self.zone.removeAssignment(self)
    self.region.removeAssignment(self)
  
  def dissolve(self): # erases the relationship only from the zone side (used when region is dissolved)
    self.zone.removeAssignment(self)

  def getZone(self):
    return self.zone
  
  def getRegion(self):
    return self.region

  def getMass(self):
    return self.zone.getMass()
  
  def getSecondaryMass(self):
    return self.zone.getSecondaryMass()
  
  def isExclave(self):
    return False
    
  def isOnlyConnection(self, diffZone): # PERFORMANCE BOTTLENECK
    '''Returns True if diffZone would change exclave status of this assignment, False otherwise.'''
    artic = self.region.getArticulation(diffZone)
    if artic: # if diffZone is an articulation point of self.region
      cores = len(self.region.getCoreZones())
      myZone = False
      for subtree in artic: # for each biconnected component separated by diffZone
        coreZone = False
        for zone in subtree:
          if zone == self.zone:
            myZone = True
          elif zone.getCore():
            coreZone = True
        if myZone: # self.zone is inside, OK if there is a core in the same component
          return (not coreZone)
        elif coreZone: # one core less to be in the same component with self.zone
          cores -= 1
          if cores == 0: return True # no core left to be in the same component as self.zone
      return False # self.zone not in separated components and so is at least one core
    else:
      return False
    
class Assignment(SimpleAssignment):
  '''An assignment of a zone to a region storing its strength and contiguity (exclave) status.'''

  def __init__(self, zone, region, core=False, degree=1, exclave=False, oscillatory=False):
    SimpleAssignment.__init__(self, zone, region)
    self.core = core
    self.degree = degree # fuzzy membership
    self.setExclave(exclave)
    # self.neighbours = set(self.zone.getNeighbours())
    self.oscillatory = oscillatory
  
  def __nonzero__(self):
    return not self.oscillatory
  
  def isCore(self):
    return self.core
  
  def getMass(self):
    return self.zone.getMass() * self.degree
  
  def getDegree(self):
    return self.degree
  
  def setDegree(self, degree):
    self.degree = degree
  
  def isExclave(self):
    return self.exclave
   
  def setExclave(self, state):
    self.exclave = state
    
  def __repr__(self):
    return '<%s as %s of %s (%g%s)>' % (self.zone, ('core' if self.core else 'hinterland'), self.region, self.degree, ', exclave' if self.exclave else '')

  def computeDegree(self, memName):
    self.setDegree(getattr(self, memName))
  
  def hamplMembership(self):
    '''Returns assignment degree (Hampl membership function).'''
    # flows = self.zone.getMutualFlows()
    # if self.core:
      # iR, dR = flows.sumsByRegion(self.region)
    # else:
      # iR, dR = flows.sumsByCore(self.region)
    # try:
      # if self.exclave:
        # penal = self.zone.getPenalization(self.exclave)
        # if penal == 0:
          # return 0
        # else:
          # return penal * iR / float(iR + dR)
      # else:
        # return iR / float(iR + dR)
    # except ZeroDivisionError:
      # return 0
    return self.zone.hamplMembership(self.region, penal=self.zone.getPenalization(self.exclave))
  
  # def getFuzzyColor(self):
    # return self.region.getColor() * self.degree
  
  def getHamplMassDiff(self, diffZone): # TODO: could use some cleaning
    '''Returns a difference that diffZone would make in the membership mass of this zone to its region.'''
    flows = self.zone.getMutualFlows()
    if flows:
      if self.core: # no exclave penalization (is on the other side of the relationship)
        if diffZone in flows:
          try:
            return self.zone.getMass() * (flows[diffZone] / float(flows.sumsByRegion(self.region)))
          except ZeroDivisionError:
            return 0
        else:
          return 0
      else: # hinterland zone
        # with diffZone in self.region: m_i * d_i(self.zone) = mc/(c+o)
        # without it: mce/(c+o+d) -> deltaEMW = mc (1/(c+o) - e/(c+o+d))
        if diffZone == self.zone: return 0 # no difference concerning me; it is counted elsewhere
        allPenal = self.zone.getPenalization(True)
        if diffZone in flows: # if any interaction relation at all
          toZone = flows[diffZone] # d
        elif allPenal != 1: # if possible neighbourhood difference
          toZone = 0
        else:
          return 0
        # get neighbourhood difference
        penal = allPenal if (allPenal != 1 and diffZone in self.zone.getNeighbours() and self.isOnlyConnection(diffZone)) else 1 # e
        if not toZone and penal == 1: # no neighbourhood difference and no interaction relation
          return 0
        toCore, outOfRegion = flows.sumsByCore(self.region) # c, o
        if not diffZone.isInRegion(self.region):
          outOfRegion -= toZone
        # common.debug('%s %s %s %s %s %s' % (toCore, outOfRegion, toZone, self.zone, penal, (self.zone.getMass() * toCore * (1 / float(toCore + outOfRegion) - penal / float(toCore + outOfRegion + toZone)))))
        try:
          return self.zone.getMass() * toCore * (1 / float(toCore + outOfRegion) - penal / float(toCore + outOfRegion + toZone))
        except ZeroDivisionError:
          return 0  
    else:
      return 0

class AssignmentPreset:
  def __init__(self, zoneID, regID, core):
    self.zoneID = zoneID
    self.regID = regID
    self.core = core
  
  def getCoreState(self):
    return self.core
    
  def getZoneID(self):
    return self.zoneID
  
  def getRegionID(self):
    return self.regID
    
      
class Region(RegionalUnit):
  def __init__(self, id):
    RegionalUnit.__init__(self, id)
    self.assignments = []
    self.indepOverride = False
    self.articulations = None
    self._mass = 0
  
  def setID(self, id):
    self.id = id
  
  def __nonzero__(self):
    '''The region is True if it contains any zone (any assignment).'''
    return bool(self.assignments)
  
  def addAssignment(self, assignment):
    '''Adds the assignment, updates the mass and resets the articulation point list.'''
    self.assignments.append(assignment)
    self._addMass(assignment)
    self.articulations = None

  def removeAssignment(self, assignment):
    '''Removes the assignment, updates the mass and resets the articulation point list.'''
    if assignment in self.assignments:
      self.assignments.remove(assignment)
      self._subMass(assignment)
      self.articulations = None
    else:
      pass # throw error if invalid?
  
  def getAssignments(self):
    return self.assignments
  
  def getZones(self):
    return [ass.getZone() for ass in self.assignments if ass]
  
  def getMass(self):
    return self._mass
    
  # expects: zone in self.getContiguousZones()
  def getArticulation(self, zone):
    '''Returns a list of biconnected hinterland components that zone separates from the region core, None if no such components exist.'''
    if zone.isInRegion(self): # splitting zone from self
      if self.articulations is None:
        self.articulations = self.calcArticulations()
      if zone in self.articulations:
        return self.articulations[zone]
      else:
        return None
    else: # adding zone to self
      excl = self.getExclaves()
      if excl: # must also be a contiguous zone
        connected = [zone]
        for exc in excl:
          for conn in connected:
            if exc.hasNeighbour(conn):
              connected.append(exc)
        del connected[0]
        if connected:
          return [connected]
        else:
          return None
      else:
        return None
  
  def getArticulations(self):
    if self.articulations is None:
      self.articulations = self.calcArticulations()
    return self.articulations
  
  def calcArticulations(self):
    '''Calculates region articulation points - zones that would cause some other hinterland zones of the region to bacome exclaves.'''
    if not self.assignments: return []
    artic = defaultdict(list) # articulation points and portions they hide from the start zone
    togo = [] # DFS stack
    ins = {} # enter time of DFS
    lows = {} # lowpoint function
    neighs = {} # neighbourhood list
    children = defaultdict(list) # DFS tree children of given zones
    # find start zone and load neighbour matrix
    for ass in self.assignments:
      if not ass.isExclave():
        zone = ass.getZone()
        if not togo: togo.append(zone)
        neighs[zone] = [neigh for neigh in zone.getNeighbours() if neigh.isInContiguousRegion(self)]
    # start DFS
    root = togo[-1]
    counter = 0
    while togo:
      now = togo[-1]
      if now not in ins: # enter vertex
        ins[now] = counter
        lows[now] = counter
        counter += 1
      for neigh in neighs[now]: # add all unvisited neighbours to stack
        if neigh not in ins:
          children[now].append(neigh)
          togo.append(neigh)
          break
      else: # exit vertex (if no unvisited neighbours found)
        if now is not root: # root has different articulation procedures
          counter += 1
          for neigh in neighs[now]: # all have been visited; update lowpoint
            if lows[neigh] < lows[now]:
              lows[now] = lows[neigh]
          for neigh in neighs[now]: # check if neigh is articulation
            if lows[neigh] >= ins[now]:
              for sub in artic[now]:
                if neigh in sub:
                  break
              else:
                artic[now].append(self.subtree(children, neigh)) # get what neigh separates from now
            elif now not in children[neigh] and lows[now] > ins[neigh]:
              lows[now] = ins[neigh]
        del togo[-1]
    for child in children[root][1:]: # if root has 2+ children, it is articulation
      artic[now].append(self.subtree(children, child))
    # if artic:
      # common.debug('articulation of %s detected: %s' % (self, artic))
    return artic
  
  @staticmethod
  def subtree(children, root):
    stack = [root]
    tree = set()
    while stack:
      now = stack.pop()
      tree.add(now)
      stack.extend(children[now])
    return tree
    
  def hasOverride(self):
    return self.indepOverride
  
  def setOverride(self, state=True):
    self.indepOverride = state
  
  def erase(self):
    '''Erases the region from all its zones.'''
    for ass in self.assignments:
      ass.dissolve()
  
  def detectExclaves(self):
    '''Detects zones that are not contiguous with the main region body (any contiguous part of the region containing at least one core is considered a region body).'''
    queue = deque(self.getCoreZones()) # not exclaves, searching their neighbours for more nonexclaves
    noconn = set(self.getAllHinterlandZones()) # yet to be connected
    while queue:
      examined = queue.popleft()
      for neigh in examined.getNeighbours():
        if neigh.isInRegion(self) and neigh in noconn:
          noconn.remove(neigh)
          queue.append(neigh)
    # anything that remained in noconn is an exclave
    # if noconn:
      # common.debug('exclaves detected at %s: %s' % (self, noconn))
    for zone in noconn:
      zone.setAssignmentExclave(self)
  
  def getExclaves(self):
    '''Returns zones that are exclaves of this region.'''
    exclaves = []
    for ass in self.assignments:
      if ass.isExclave():
        exclaves.append(ass.getZone())
    return exclaves
  
  def removeExclaves(self):
    '''Removes all exclaves from this region.'''
    # common.debug(self)
    # common.debug(self.assignments)
    i = 0
    while i < len(self.assignments):
      if self.assignments[i].isExclave():
        # common.debug('removing %s' % self.assignments[i])
        self.assignments[i].erase()
      else:
        i += 1
  
  def getContiguousZones(self):
    '''Returns all zones in self that are not exclaves.'''
    contig = set()
    for ass in self.assignments:
      if not ass.isExclave():
        contig.update(ass.getZone().getNeighbours())
    # arcpy.AddMessage(str(list(contig)))
    contig.difference_update(self.getZones())
    # common.debug([zone.assignments for zone in self.getZones()])
    # common.debug(contig)
    return list(contig)
  
  def getContiguousRegions(self):
    '''Returns all neighbouring regions (all regions that have at least one non-exclave zone bordering a non-exclave zone of self).'''
    contig = set()
    for ass in self.assignments:
      if not ass.isExclave():
        contig.update(ass.getZone().getContiguousRegions())
    contig.discard(self)
    return list(contig)
    
    
class PlainRegion(Region):
  def __init__(self, zone):
    Region.__init__(self, zone.getID())
    self._resetMass()
    Assignment(zone, self, core=True).tangle()

  def _addMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    self._mass += assignment.getMass()

  def _subMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    self._mass -= assignment.getMass()

  def _resetMass(self):
    self._mass = 0

  def __repr__(self):
    return '<Region {} ({} zones)>'.format(self.id, len(self.assignments))
    
    
class StaticRegion(Region):
  def __init__(self, zone, id):
    self.rigidUnit = zone.getRigidUnit()
    Region.__init__(self, id)
    self._secmass = 0
    self._location = zone.getLocation()
    SimpleAssignment(zone, self).tangle()
    self.flexibleUnit = zone.getFlexibleUnit()
    
  def _addMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    self._mass += assignment.getMass()
    secmass = assignment.getSecondaryMass()
    if secmass is None:
      if self._secmass == 0:
        self._secmass = None
    else:
      if self._secmass is None:
        self._secmass = 0
      self._secmass += secmass
    self._location = None
      
  def _subMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    self._mass -= assignment.getMass()
    secmass = assignment.getSecondaryMass()
    if secmass is not None and self._secmass is not None:
      self._secmass -= secmass
    self._location = None
  
  def _resetMass(self):
    self._mass = 0
    if self._secmass is not None:
      self._secmass = 0
    self._location = None
  
  def getSecondaryMass(self):
    return self._secmass

  def getRigidUnit(self):
    return self.rigidUnit
  
  def getFlexibleUnit(self):
    return self.flexibleUnit
  
  def getLocation(self):
    if self._location is None:
      zones = self.getZones()
      self._location = numpy.array([0, 0])
      loccount = 0
      for zone in zones:
        loc = zone.getLocation()
        if loc is not None:
          loccount += 1
          self._location += loc
      self._location /= loccount
    return self._location
  
  def distanceTo(self, other):
    diff = self.getLocation() - other.getLocation()
    return diff.dot(diff) ** 0.5
    # except ValueError:
      # return 1e15
  
  # def __repr__(self):
    # return '<Region %s (%i%s;%i zones)>' % (self.id, self.getMass(), ('/%i' % int(self.getSecondaryMass()) if self.getSecondaryMass() else ''), len(self.assignments))

  def __repr__(self):
    return '<Region %s (%i%s;%i zones: %s)>' % (self.id, self.getMass(), ('/%i' % int(self.getSecondaryMass()) if self.getSecondaryMass() else ''), len(self.assignments), ', '.join([repr(zone) for zone in self.getZones()]))

    
# a functional region with a number of cores (usually one) and a hinterland
class FunctionalRegion(Region):
  '''A multicore region to which the zones may belong only to a certain degree.'''
  interactionClass = Interactions

  def __init__(self, coreZone):
    '''Initializes the region, making the coreZone ID and color the ID and color of the region.'''
    Region.__init__(self, coreZone.getID()) 
    self._coremass = 0
    self._rawcoremass = 0 # a true mass of the core zones (no membership correction) for discriminating between zero-EMW regions
    Assignment(coreZone, self, core=True).tangle()
    zoneColor = coreZone.getColor()
    self.color = colors.BLACK_RGB if zoneColor is None else zoneColor

  def _addMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    mass = assignment.getMass()
    self._mass += mass
    if assignment.isCore():
      self._coremass += mass
      self._rawcoremass += assignment.getZone().getMass()
    self._intraflows = None
      
  def _subMass(self, assignment):
    '''Updates the mass with the mass of an assignment.'''
    mass = assignment.getMass()
    self._mass -= mass
    if assignment.isCore():
      self._coremass -= mass
      self._rawcoremass -= assignment.getZone().getMass()
    self._intraflows = None
  
  def _resetMass(self):
    self._mass = 0
    self._coremass = 0
    self._rawcoremass = 0
    self._intraflows = None
    
  def getHinterlandMass(self):
    return (self._mass - self._coremass)
  
  def getRawMass(self):
    return self._rawcoremass
  
  def getColor(self):
    return self.color
  
  def getCoreZones(self):
    cores = []
    for ass in self.assignments:
      if ass.isCore():
        cores.append(ass.getZone())
    return cores
  
  def getHinterlandZones(self):
    '''Returns all region hinterland zones whose assignment has a nonzero degree.'''
    hinter = []
    for ass in self.assignments:
      if ass and not ass.isCore():
        hinter.append(ass.getZone())
    return hinter
  
  def getAllHinterlandZones(self):
    '''Returns all region hinterland zones.'''
    hinter = []
    for ass in self.assignments:
      if not ass.isCore():
        hinter.append(ass.getZone())
    return hinter

  def getHinterlandZoneBorderings(self):
    '''Returns all border zones of the region with the list of all regions they neighbour with. Used with reassignment changes setup.'''
    borderings = defaultdict(list)
    for zone in self.getAllHinterlandZones():
      for region in zone.getContiguousRegions():
        if region is not self:
          borderings[zone].append(region)
    return borderings
       
    
  def updateAssignments(self, memName):
    '''Updates its assignments so that each has its degree set to the corresponding membership function value in the region.'''
    self._resetMass()
    for ass in self.assignments:
      ass.computeDegree(memName)
      self._addMass(ass)
  
  def updateMass(self):
    self._resetMass()
    for ass in self.assignments:
      self._addMass(ass)

  # def getBezakSC(self):
    # return self.getIntraflows().sum() / float(self.getMutualFlows())
  
  # def getCoombesSC(self):
    # intra = self.getIntraflows().sum()
    # return intra / float(intra + self.getOutflows().sum()) + intra / float(intra + self.getInflows().sum())
      
  def getOutflows(self, core=True, hinter=True):
    '''Returns outflows from given parts of the region out of the region.'''
    # oscilacni zony se nepocitaji jako region...
    src = (self.getCoreZones() if core else []) + (self.getHinterlandZones() if hinter else [])
    # common.debug(self, core, hinter, src)
    # common.debug(self.interactionClass.outflowsFrom(src))
    # common.debug(self.interactionClass.outflowsFrom(src).exclude(self.getZones()))
    return self.interactionClass.outflowsFrom(src).exclude(self.getZones())

  def getInflows(self, core=True, hinter=True):
    zones = (self.getCoreZones() if core else []) + (self.getHinterlandZones() if hinter else [])
    return self.interactionClass.inflowsTo(zones).exclude(self.getZones())
  
  def getMutualFlows(self, core=True, hinter=True):
    return (self.getInflows(core=core, hinter=hinter) + self.getOutflows(core=core, hinter=hinter)).exclude(self.getZones())
  
  def _getIntraflows(self, fromCore=True, fromHinter=True, toCore=True, toHinter=True):
    '''Returns outflows from given parts of the region into the region.'''
    # oscilacni zony se nepocitaji jako region...
    fromZones = (self.getCoreZones() if fromCore else []) + (self.getHinterlandZones() if fromHinter else [])
    toZones = (self.getCoreZones() if toCore else []) + (self.getHinterlandZones() if toHinter else [])
    return self.interactionClass.outflowsFrom(fromZones).restrict(toZones)
  
  def getIntraflows(self, **kwargs):
    if kwargs:
      return self._getIntraflows(**kwargs)
    else:
      if self._intraflows is None:
        self._intraflows = self._getIntraflows()
      return self._intraflows

  # def getCoreHintFlows(self):
    # '''Returns flows from core to hinterland.'''
    # return self._getIntraflows(fromHinter=False, toCore=False)
  
  # def getHintCoreFlows(self):
    # '''Returns flows from hinterland to core.'''
    # return self._getIntraflows(fromCore=False, toHinter=False)
  
  def getFlowSum(self):
    return sum(zone.getOutflows().sum() for zone in self.getZones())
  
  def getEMWDiff(self, zone):
    '''Returns a difference in region EMW the reassignment of zone into/out of the region would make.'''
    return sum(ass.getHamplMassDiff(zone) for ass in self.assignments) + zone.hamplMembershipMass(self, penal=zone.getPenalizationDiff(self))
  
  def getMembershipIn(self, memName, region):
    '''Returns a sum of membership masses of its zones in the specified other region. Used to calculate region overlap.'''
    return sum(ass.getZone().membershipMass(memName, region) for ass in self.assignments)
  
  def getHamplMembershipIn(self, region):
    '''Returns a sum of membership masses of its zones in the specified other region. Used to calculate region overlap.'''
    return self.getMembershipIn('hamplMembership', region)
    
  def __repr__(self):
    return '<Region %s (%i;%i;%i zones)>' % (self.id, self.getMass(), self.getHinterlandMass(), len(self.assignments))
    
  def emw(self):
    w = 0
    for ass in self.assignments:
      zone = ass.getZone()
      w += zone.hamplMembershipMass(self, zone.getPenalization())
    return w
  
  def fmw(self):
    w = 0
    cores = []
    # all cores' membership masses
    for ass in self.assignments:
      if ass.isCore():
        zone = ass.getZone()
        w += zone.hamplMembership(self, zone.getPenalization())
        cores.append(zone)
    # all other zones' affiliations to the region (membership is zero if the core outflow is zero)
    inflows = self.interactionClass.inflowsTo(cores).exclude(cores)
    for source in inflows:
      w += source.hamplMembership(self, inflows[source], zone.getPenalizationDiff(self)) * source.getMass()
    return w

    
# a unit that contains zones and limits region growth
class AdministrativeUnit(RegionalUnit):
  def __repr__(self):
    return '<AdministrativeUnit {}>'.format(self.id)
 
 
class Loader(object):
  '''A pseudo-abstract loader class used to load all kinds of data into the program.'''

  fieldSlots = []
  divQuery = ''
  noQuery = ''
  sortFields = ''
  targetClass = tuple
 
  def __init__(self, layer, fieldNames):
    '''Initializes the loader to the given source. Does not yet open or load anything.'''
    self.layer = layer
    self.origLayer = layer
    # common.progress('loading %s: %i objects' % (self.layer, self.getLayerCount()))
    self.fieldNames = fieldNames
    self.count = 0
  
  def addDivLoad(self, query):
    '''Adds a where condition to divide loading into two classes - yesClass and noClass - by the condition.'''
    self.divQuery = query
  
  def addNoLoad(self, query):
    '''Adds a where condition that suppresses loading of some records.'''
    self.noQuery = query
  
  def setTargetClass(self, cls):
    '''Sets the class to load.'''
    self.targetClass = cls
 
  def parseRow(self, row):
    '''Extracts the values from the record and passes them backs as list.'''
    results = []
    for field in self.fieldNames:
      if field in (None, ''):
        results.append(None)
      elif field == 'ZEROFILL':
        results.append(0)
      else:
        results.append(row.getValue(field))
      self.count += 1
    return results
  
  def getObject(self, row, div=None):
    '''Returns an object of the current default type initialized with the given row contents.'''
    out = self.targetClass(*self.parseRow(row))
    if div is not None:
      setattr(out, self.divParam, div)
    return out
      
  # def getOtherObject(self, row, cls, divParam=tuple()):
    # '''Returns an instance of the given class initialized with the given row contents.'''
    # out = cls(*self.parseRow(row))
    # for param, value in divParam:
      # setattr(out, param, value)
    # return out

  def getCount(self):
    '''Returns a number of records loaded.'''
    return self.count

  def getLayerCount(self):
    '''Returns a number of records in the underlying layer.'''
    return common.count(self.layer)

  def field(self, slot):
    return self.fieldNames[self.fieldSlots.index(slot)]
  
  def load(self):
    '''Loads the layer contents. If divQuery or noQuery is on, differentiates the loading. Calls loadGroup().'''
    if self.noQuery:
      newLayer = 'tmp_' + str(id(self))
      arcpy.MakeTableView_management(self.layer, newLayer, self.noQuery)
      self.layer = newLayer
    if self.divQuery:
      self.loadGroup(self.divQuery, True)
      self.loadGroup(common.invertQuery(self.divQuery), False)
    else:
      self.loadGroup()
  
  def loadGroup(self, query='', div=None):
    '''Establishes a SearchCursor above the layer with the given query and loads the data obtained from it to the objects of the class.'''
    cursor = arcpy.SearchCursor(self.layer, query, '', '', self.sortFields)
    for row in cursor:
      self.loadObject(row, div)

      
class ZoneLoader(Loader):
  '''A zone loader and output writer.'''

  targetClass = MonoZone
  divParam = 'coreable'
  
  def __init__(self, layer, fieldNames, presets=None):
    Loader.__init__(self, layer, fieldNames)
    self.presetFields = presets
    self.presets = []
 
  def load(self):
    self.zones = {}
    Loader.load(self)
    return self.zones

  def loadObject(self, row, div=None):
    zone = self.getObject(row, div)
    id = zone.getID()
    if self.presetFields:
      self.loadPresets(id, row)
    self.zones[id] = zone
 
  def loadOtherObject(self, row, cls, div=None):
    zone = self.getOtherObject(row, cls, div)
    id = zone.getID()
    if self.presetFields:
      self.loadPresets(id, row)
    self.zones[id] = zone
 
  def loadPresets(self, id, row):
    for field in self.presetFields:
      val = row.getValue(field)
      if val:
        self.presets.append(AssignmentPreset(id, val, self.presetFields[field]))
  
  def getPresets(self):
    return self.presets
 
  def output(self, zones, outFld=None, coopFld=None, exclaveFld=None, colorFld=None, measures=[]):
    '''Outputs all kinds of zone information possible - regional assignment to outFld (including secondary cores to coopFld), exclave status to exclaveFld, membership color to colorFld and various measure values.
    Adds fields to the zones table and fills them with data.'''
    for zone in zones.values():
      zone.transferExclaveFlag()
    outType = common.fieldType(type(zones.values()[0].getID()))
    fields = common.fieldList(self.origLayer)
    if outFld and outFld not in fields:
      arcpy.AddField_management(self.origLayer, outFld, outType)
    if coopFld and coopFld not in fields:
      arcpy.AddField_management(self.origLayer, coopFld, outType)
    if exclaveFld and exclaveFld not in fields:
      arcpy.AddField_management(self.origLayer, exclaveFld, 'SHORT')
    if colorFld and colorFld not in fields:
      arcpy.AddField_management(self.origLayer, colorFld, 'TEXT')
    measurer = ZoneMeasurer(measures, regName=outFld)
    measurer.createOutputFields(self.origLayer, next(zones.itervalues()), exclude=fields)
    zoneCursor = arcpy.UpdateCursor(self.origLayer)
    for zoneRow in zoneCursor:
      zone = zones[zoneRow.getValue(self.fieldNames[0])]
      if outFld:
        region = zone.getRegion()
        if region:
          zoneRow.setValue(outFld, region.getID())
        else:
          zoneRow.setValue(outFld, None)
      if coopFld:
        zoneRow.setValue(coopFld, zone.getLesserCoreID())
      if exclaveFld:
        zoneRow.setValue(exclaveFld, zone.getExclaveFlag())
      if colorFld:
        zoneRow.setValue(colorFld, zone.getColorHex())
      zoneRow = measurer.outputMeasures(zone, zoneRow)
      zoneCursor.updateRow(zoneRow)
  
  def outputMultiMeasures(self, zones, fieldNames, measures, aliases=[]):
    '''Outputs the given zone measures that give interaction vectors as results.'''
    # we need some example values to base field types on
    firstZone = next(zones.itervalues())
    # add the fields
    names = {}
    for i in range(len(measures)):
      vector = iter(firstZone.getMeasure(measures[i])) # a resulting type vector
      names[measures[i]] = []
      for fld in fieldNames:
        if i < len(aliases):
          names[measures[i]].append((fld + '_' + aliases[i], type(next(vector))))
        else:
          names[measures[i]].append((fld + '_' + measures[i], type(next(vector))))
    for fields in names.itervalues():
      common.addFields(self.origLayer, fields)
    # open zones for updating
    zoneCursor = arcpy.UpdateCursor(self.origLayer)
    # calculate the measures and write them right away
    for zoneRow in zoneCursor:
      zone = zones[zoneRow.getValue(self.fieldNames[0])]
      for measure in measures:
        result = zone.getMeasure(measure)
        for i in range(len(result)):
          zoneRow.setValue(names[measure][i][0], result[i])
      zoneCursor.updateRow(zoneRow)
        
  
  @staticmethod
  def measureField(reg, name):
    if reg:
      return reg + '_' + name
    else:
      return name

class MultiZoneLoader(ZoneLoader):
  targetClass = MultiZone

  
class BaseInteractionLoader(Loader):
  '''A pseudo-abstract class for interaction loaders. Interactions are loaded as zone inflows and outflows.'''

  def load(self, zones):
    self.failedSources = 0
    self.failedTargets = 0
    self.zones = zones
    Loader.load(self)
    if self.failedSources:
      common.warning('%i interactions failed to load due to unknown origin ID, used as unknown inflows' % self.failedSources)
    if self.failedTargets:
      common.warning('%i interactions\' targets failed to load due to unknown target ID, used as unknown outflows' % self.failedTargets)

  def loadObject(self, row, div=None):
    source, target, strength = self.parseValues(row)
    if strength:
      if source and target:
        source.addOutflow(target, strength)
        target.addInflow(source, strength)
        self.count += 1
      else:
        if source:
          self.failedTargets += 1 # target not found
          source.addRawOutflow(strength)
        elif target:
          self.failedSources += 1 # origin not found
          target.addRawInflow(strength)

class InteractionLoader(BaseInteractionLoader):
  '''Loads ordinary interactions to zone outflows and inflows. Expects only one interaction strength.'''

  fieldSlots = ['strength', 'fromID', 'toID']
  targetClass = None
  
  def load(self, zones):
    self.sortFields = self.fieldNames[0] + ' D'
    BaseInteractionLoader.load(self, zones)
  
  def parseValues(self, row):
    try:
      source = self.zones[row.getValue(self.fieldNames[1])]
    except KeyError:
      source = None
    try:
      target = self.zones[row.getValue(self.fieldNames[2])]
    except KeyError:
      target = None
    strength = row.getValue(self.fieldNames[0])
    return (source, target, strength)
  
  # does not expect more than 30k interactions per zone (short) - should be well within bounds
  # could be probably sped up a lot
  def outputOrders(self, zones, ordFld=None, relFld=None):
    '''Outputs interactions' relative strength for the given origin.'''
    if ordFld:
      arcpy.AddField_management(self.origLayer, ordFld, 'SHORT')
    if relFld:
      arcpy.AddField_management(self.origLayer, relFld, 'DOUBLE')
    cursor = arcpy.UpdateCursor(self.origLayer)
    for row in cursor:
      try:
        source = self.zones[row.getValue(self.fieldNames[1])]
      except KeyError:
        source = None
      try:
        target = self.zones[row.getValue(self.fieldNames[2])]
      except KeyError:
        target = None
      if source:
        if target:
          try:
            if ordFld:
              row.setValue(ordFld, source.getOutflowIndex(target) + 1)
            if relFld:
              row.setValue(relFld, source.getRelativeOutflow(target))
          except IndexError:
            pass # outflow not found
        else:
          if relFld:
            row.setValue(relFld, source.getRawOutflowPercent())
      cursor.updateRow(row)
      
class MultiInteractionLoader(BaseInteractionLoader):
  '''A loader for interactions with multiple strengths.'''

  fieldSlots = ['fromID', 'toID', 'strength1', 'strength2']
  targetClass = InteractionVector
  
  def load(self, zones):
    self.sortFields = self.fieldNames[0]
    BaseInteractionLoader.load(self, zones)
  
  def parseValues(self, row):
    try:
      source = self.zones[row.getValue(self.fieldNames[0])]
    except KeyError:
      source = None
    try:
      target = self.zones[row.getValue(self.fieldNames[1])]
    except KeyError:
      target = None
    vec = InteractionVector()
    for fld in self.fieldNames[2:]:
      vec.append(row.getValue(fld))
    return (source, target, vec)
  
  def getStrengthFieldNames(self):
    return self.fieldNames[2:]
  
  def outputDict(self, flows, outDir, outName):
    '''Outputs the given interactions (flows) into a new interaction table defined by a location and name. Flows are expected to be in a dict(Zone : Interactions).'''
    # create a table with OD IDs and value fields
    output = arcpy.CreateTable_management(outDir, outName).getOutput(0)
    # we need some example values to base field types on
    firstKey = next(flows.iterkeys()) 
    idType = common.fieldType(type(firstKey.getID()))
    # some arbitrary InteractionVector to browse types
    valIter = iter(flows[firstKey][next(flows[firstKey].iterkeys())])
    # add the fields
    arcpy.AddField_management(output, self.fieldNames[0], idType)
    arcpy.AddField_management(output, self.fieldNames[1], idType)
    for fld in self.getStrengthFieldNames():
      arcpy.AddField_management(output, fld, common.fieldType(type(next(valIter))))
    # fill in the data
    outCur = arcpy.InsertCursor(output)
    for source in flows:
      for target in flows[source]:
        row = outCur.newRow()
        row.setValue(self.fieldNames[0], source.getID())
        row.setValue(self.fieldNames[1], target.getID())
        i = 0
        for fld in self.fieldNames[2:]: # value fields
          row.setValue(fld, flows[source][target][i])
          i += 1
        outCur.insertRow(row)
    del outCur
      
      
class NeighbourLoader(Loader):
  '''Loads neighbourhood relationships from the given neighbourhood table, expecting two identifier fields. Does not impose two-way neighbourhood constraint.'''

  def __init__(self, layer):
    # fields = arcpy.ListFields(layer)
    # if len(fields) < 2: raise ValueError, 'not enough fields in the neighbourhood table'
    Loader.__init__(self, layer, [common.NEIGH_FROM_FLD, common.NEIGH_TO_FLD])
 
  def load(self, zones):
    self.zones = zones
    Loader.load(self)
  
  def loadObject(self, row, div=None):
    try:
      self.zones[row.getValue(self.fieldNames[0])].addNeighbour(self.zones[row.getValue(self.fieldNames[1])])
    except KeyError, fail:
      raise ValueError, 'invalid zone ID in the neighbourhood table: %s' % fail


class PointGeometryLoader(Loader):
  '''Loads zone point locations from the given point feature class according to the identifier provided. Unknown identifier values in the point feature class are ignored.'''

  def __init__(self, layer, idFld):
    shpFld = arcpy.Describe(layer).ShapeFieldName
    Loader.__init__(self, layer, [idFld, shpFld])
    global numpy
    import numpy
 
  def load(self, zones):
    self.zones = zones
    Loader.load(self)
  
  def loadObject(self, row, div=None):
    try:
      self.zones[row.getValue(self.fieldNames[0])].setLocation(self.parseLocation(row.getValue(self.fieldNames[1])))
    except KeyError, fail:
      pass
      # raise ValueError, 'invalid zone ID in the point geometry layer: %s' % fail

  def parseLocation(self, shape):
    if shape is None:
      return None
    else:
      part = shape.getPart()
      return numpy.array([part.X, part.Y])
      

class OverlapWriter:
  OVERLAP_FLD = 'OVERLAP'
  
  def __init__(self, path):
    self.path = path
  
  def createTable(self, path, idType):
    common.createTable(path)
    arcpy.AddField_management(path, common.NEIGH_FROM_FLD, common.pyTypeToOut(idType))
    arcpy.AddField_management(path, common.NEIGH_TO_FLD, common.pyTypeToOut(idType))
    arcpy.AddField_management(path, self.OVERLAP_FLD, common.pyTypeToOut(float))
  
  def writeTable(self, overlapDict):
    self.createTable(self.path, idType=type(next(overlapDict.iterkeys()).getID()))
    cur = arcpy.InsertCursor(self.path)
    fromFld = common.NEIGH_FROM_FLD
    toFld = common.NEIGH_TO_FLD
    overlapFld = self.OVERLAP_FLD
    for region, neighDict in overlapDict.iteritems():
      fromID = region.getID()
      for neigh, overlap in neighDict.iteritems():
        row = cur.newRow()
        row.setValue(fromFld, fromID)
        row.setValue(toFld, neigh.getID())
        row.setValue(overlapFld, overlap)
        cur.insertRow(row)
    del cur
        
      
class BaseRegionaliser:
  def __init__(self, zones):
    self.zones = zones
    self.regions = []
  
  def findRegion(self, regID):
    # dirty but sure works for any sorting
    for reg in self.regions:
      if reg.getID() == regID:
        return reg
    return None
  
  def getRegions(self):
    return self.regions
  
  def getZones(self):
    return list(self.zones.values())

  # debug procedures for listing the current state
  def debugZones(self):
    for zone in self.zones.values():
      common.debug(zone)
      common.debug(zone.getAssignments())
  
  def debugAss(self):
    for zone in self.zones.values():
      for ass in zone.getAssignments():
        common.debug(ass)
  
  def tangleAssignment(self, ass):
    raise NotImplementedError
  
  def updateAssignments(self):
    pass
  
  def createRegions(self, regClass=FunctionalRegion):
    '''Creates regions for its zones. For every coreable zone, a region is created.'''
    self.regions = []
    for zone in self.zones.values(): # region for each core zone
      if zone.coreable:
        self.regions.append(regClass(zone))
    self.regions.sort(key=ID_SORTER)

  def verify(self, region):
    # must pass all verifications in at least one simultaneous group
    for criterion in self.verificationCriteria:
      if isinstance(criterion, Criterion):
        result = criterion.verify(region)
      else:
        result = False
        for verifier in criterion:
          result = result or verifier.verify(region)
      if not result:
        return False
    return True
  
  def verifyTimes(self, region, times):
    # must pass all verifications in at least one simultaneous group
    for criterion in self.verificationCriteria:
      if isinstance(criterion, Criterion):
        result = criterion.verifyTimes(region, times)
      else:
        result = False
        for verifier in criterion:
          result = result or verifier.verifyTimes(region, times)
      if not result:
        return False
    return True
    
  def verifyTogether(self, units):
    # must pass all verifications in at least one simultaneous group
    for criterion in self.verificationCriteria:
      if isinstance(criterion, Criterion):
        result = criterion.verifyTogether(units)
      else:
        result = False
        for verifier in criterion:
          result = result or verifier.verifyTogether(units)
      if not result:
        return False
    return True
    
  def verifyWithout(self, region, zone):
    # must pass all verifications in at least one simultaneous group
    for criterion in self.verificationCriteria:
      if isinstance(criterion, Criterion):
        result = criterion.verifyWithout(region, zone)
      else:
        result = False
        for verifier in criterion:
          result = result or verifier.verifyWithout(region, zone)
      if not result:
        return False
    return True
      
  def generateNeighbourTable(self, zones, zoneIDFld):
    from conversion import SpatialMatrixNeighbourLinker
    linker = SpatialMatrixNeighbourLinker(zones, zoneIDFld, 'CONTIGUITY_EDGES_ONLY', common.location(zones), messenger=common.MutedMessenger())
    linker.process()
    neighTable = linker.output(self.TMP_NEIGH_TABLE)
    linker.close()
    return neighTable


    
class StaticAggregationRegionaliser(BaseRegionaliser):
  TMP_NEIGH_TABLE = 'tmp_neigh'
  
  @staticmethod
  def sortByMass(lst):
    '''Sorts the list of RegionalUnits uniquely according to their masses.'''
    lst.sort(key=ID_SORTER)
    lst.sort(key=SECONDARY_MASS_SORTER)
    lst.sort(key=MASS_SORTER)
  
  def hasZeroWeight(self, item):
    '''Checks if the RegionalUnit provided has zero weight (zero primary and secondary mass).'''
    mass = item.getMass()
    secmass = item.getSecondaryMass()
    return bool(mass == 0 and (secmass is None or secmass == 0))
  
  def createRegions(self):
    '''Creates regions for its zones. Higher level administrative units are created as well.'''
    zones = self.getZones()
    maxI = self.generateUnits(zones)
    self.calculateOutputIDs(maxI)
    self.generateRegions(zones)
  
  def generateRegions(self, zones):
    self.regions = []
    zones.sort(key=operator.methodcaller('getRigidUnitID'))
    prevUnitID = False
    for zone in zones:
      # generate region ID from rigid unit ID (if present)
      unit = zone.getRigidUnit()
      unitID = unit.getID()
      if unitID != prevUnitID:
        i = 1
        prevUnitID = unitID
      else:
        i += 1
      self.regions.append(StaticRegion(zone, ('' if unitID is None else unitID) + self.formatter.format(i)))
  
  def generateUnits(self, zones):
    self.rigidUnits, maxI = self.makeUnitSet(zones, operator.methodcaller('getRigidUnitID'), 'setRigidUnit')
    self.flexibleUnits, maxI2 = self.makeUnitSet(zones, operator.methodcaller('getFlexibleUnitID'), 'setFlexibleUnit')
    return maxI
  
  @staticmethod
  def makeUnitSet(zones, idGetter, unitSetterName):
    units = []
    prevUnitID = 'UNMATCHABLE' # something that should never occur
    i = 0
    maxI = 1
    zones.sort(key=idGetter) # sort by respective unit ID to assign sequentially
    for zone in zones:
      unitID = idGetter(zone)
      if unitID != prevUnitID:
        if i > maxI: maxI = i
        i = 1
        unit = AdministrativeUnit(unitID)
        units.append(unit)
        prevUnitID = unitID
      else:
        i += 1
      getattr(zone, unitSetterName)(unit)
    if i > maxI: maxI = i
    return units, maxI
  
  def calculateOutputIDs(self, maxSubunits):
    '''Creates a formatting string for the last part of the aggregate IDs being created.
    Determines the necessary number of decimal places.'''
    import math
    self.subunitPlaces = int(math.ceil(math.log10(maxSubunits)))
    self.formatter = '{{:0{}d}}'.format(self.subunitPlaces)
  
  def setVerificationThresholds(self, threshMass, secondaryThreshMass):
    self.exhausted = []
    self.leaks = []
    self.verificationCriteria = [MainMassVerifier(threshMass)]
    if secondaryThreshMass:
      self.verificationCriteria.append(SecondaryMassVerifier(secondaryThreshMass))
  
  def aggregate(self, locationFallback=False):
    '''Aggregates the regions so that they all fulfill the two conditions:
    - mass above threshMass and
    - secondary mass above secondaryThreshMass
    Uses a simple heuristic aggregating to the smallest available neighbour that
    causes the aggregate to cross the threshold.'''
    # common.debug(self.leaks)
    if locationFallback: self.leaks = [] # reset leaks, location fallback removes them
    self.sortByMass(self.regions) # aggregate smallest first
    # common.debug(self.regions)
    i = 0
    while i < len(self.regions):
      if not (self.verify(self.regions[i]) or self.handleZero(self.regions[i])):
        # common.debug('aggregating %s' % self.regions[i])
        move = self.assignRegion(self.regions[i], self.targetByNeighbourhood)
        if move: # some aggregation performed
          self.regions.pop(i)
          i -= move
          self.sortByMass(self.regions)
        elif self.rigidUnitExhausted(self.regions[i]): # no target within rigid unit
          # common.debug('%s exhausted' % self.regions[i])
          self.exhausted.append(self.regions[i])
          self.regions[i].setOverride()
        elif locationFallback:
          move = self.assignRegion(self.regions[i], self.targetByLocation)
          if move: # some aggregation performed
            self.regions.pop(i)
            i -= move
            self.sortByMass(self.regions)
          else: # logical error, must find some (or else rigid unit is exhausted)
            self.regions[i].setOverride()
            common.warning('Aggregation failed for region {reg}, left independent'.format(reg=self.regions[i].getID()))
        else:
          # no override set, will be aggregated in the next step, if applicable
          self.leaks.append(self.regions[i])
          # common.warning('Region {reg} is an exclave of rigid superunit {unit}, left independent: potential data leak'.format(reg=self.regions[i].getID(), unit=self.regions[i].getRigidUnit().getID()))
      # else:
        # common.message('%s independent' % self.regions[i])
      i += 1
    self.dropZeros()
  
  def report(self):
    zeros = sum(1 for reg in self.regions if self.hasZeroWeight(reg))
    if zeros:
      common.warning('{} empty zones left independent'.format(zeros))
    if self.exhausted:
      common.warning('{count} rigid superunits ({units}) are smaller than the specified threshold, left independent'.format(count=len(self.exhausted), units=', '.join(reg.getRigidUnit().getID() for reg in self.exhausted)))
    if self.leaks:
      leakUnits = frozenset(reg.getRigidUnit().getID() for reg in self.leaks)
      common.warning('{count} exclaves ({regions}) of rigid units {units} are smaller than the specified threshold, left independent: potential data leak'.format(count=len(self.leaks), regions=', '.join(reg.getID() for reg in self.leaks), units=', '.join(leakUnits)))
  
  def hasLeaks(self):
    return bool(self.leaks)
  
  def rigidUnitExhausted(self, region):
    regUnit = region.getRigidUnit()
    for compReg in self.regions:
      if compReg.getRigidUnit() is regUnit and compReg is not region:
        return False
    return True
  
  def dropZeros(self):
    '''Drops zero weight zones from regions that do not require them for contiguity
    and creates new single-zone regions for them.'''
    for region in self.regions:
      if not self.hasZeroWeight(region):
        self.dropZeroZonesFrom(region)
      
  def dropZeroZonesFrom(self, region):
    # all zero mass zones
    zeros = [zone for zone in region.getZones() if self.hasZeroWeight(zone)]
    self.sortByMass(zeros) # assure stable unique ordering
    stop = False
    while zeros:
      zero = zeros.pop()
      # that would not cause the region to break into two parts
      if not region.getArticulation(zero):
        # make their own region back
        unused = self.getUnusedID(zero.getRigidUnit())
        zero.deassign()
        self.regions.append(StaticRegion(zero, unused))
        # SimpleAssignment(zero, self.regions[-1]).tangle()
  
  def getUnusedID(self, unit):
    '''Finds an ID for the region with respect to its administrative unit belonging.
    Tries to minimize the suffix number.'''
    unitID = unit.getID()
    if unitID is None: unitID = ''
    i = 1
    while True:
      tryID = unitID + self.formatter.format(i)
      if self.findRegion(tryID):
        i += 1
      else:
        return tryID 
  
  def handleZero(self, region):
    # common.debug('%s: %s' % (region, self.hasZeroWeight(region)))
    if self.hasZeroWeight(region):
      region.setOverride()
      return True
    else:
      return False
  
  def assignRegion(self, region, searchFx):
    # try within the flexible unit first
    tgt = searchFx(region, crossFlexible=False)
    # only after preferring merges within flexible unit, drop this preference
    if not tgt: 
      tgt = searchFx(region, crossFlexible=True)
    # common.debug(tgt)
    if tgt: # if any target found, merge them
      for ass in region.getAssignments():
        SimpleAssignment(ass.getZone(), tgt).tangle()
      region.erase()
      if tgt.hasOverride(): # remove the override if merged into one (needs re-checking)
        tgt.setOverride(False)
      if tgt.getMass() == region.getMass() and tgt.getSecondaryMass() == region.getSecondaryMass():
        return 2 # need to re-check the result (no mass improvement)
      else:
        return 1
    else:
      # no targets found, can't do anything (probably rigid unit limits reached)
      return 0
  
  def targetByNeighbourhood(self, region, crossFlexible=False, omitZeros=True):
    rigidUnit = region.getRigidUnit()
    flexUnit = region.getFlexibleUnit()
    minMass = 9e18 # simply a huge number
    minReg = None
    candidates = []
    for reg in region.getContiguousRegions(): # neighbouring regions
      # must be within the same rigid unit (and flexible unit, if not crossFlexible)
      if reg is not None and reg.getRigidUnit() is rigidUnit and (crossFlexible or reg.getFlexibleUnit() is flexUnit):
        # looking for the smallest neighbour
        if not omitZeros or reg.getMass() > 0:
          candidates.append(reg)
    # common.debug('candidates for %s: %s' % (region, candidates))
    if candidates:
      self.sortByMass(candidates)
      for cand in candidates:
        if self.verifyTogether([cand, region]): # if minimum mass is reached
          return cand
      return candidates[0] # if none over threshold found, try the smallest one
    elif omitZeros: # try second time, merging zero mass regions first to get to some valid targets within unit
      return self.targetByNeighbourhood(region, crossFlexible=crossFlexible, omitZeros=False)
    else:
      return None
  
  def targetByLocation(self, region, crossFlexible=False):
    rigidUnit = region.getRigidUnit()
    flexUnit = region.getFlexibleUnit()
    candidates = {}
    for cand in self.regions:
      if cand is not None and cand.getRigidUnit() is rigidUnit and (crossFlexible or cand.getFlexibleUnit() is flexUnit) and cand is not region:
        candidates[cand] = region.distanceTo(cand)
    # common.debug('LOCATIONAL candidates for %s: %s' % (region, candidates))
    if candidates:
      return min(candidates.iteritems(), key=operator.itemgetter(1))[0]
    else:
      return None
      
      
    

    
class ZoneMeasurer:
  def __init__(self, names=[], regName=None):
    self.names = names
    self.dedicatedMeasurer = RegionMeasurer()
    self.outputNames = self.createOutputNameDict(names, regName).items()

  def getMeasure(self, object, name):
    # common.message(name)
    # common.message(self.measureMethods.keys())
    if name not in self.measureMethods:
      measure = self.dedicatedMeasurer.getDedicatedMeasure(object, name)
    else:
      measure = self.measureMethods[name](object)
    return measure.getID() if isinstance(measure, RegionalUnit) else measure
  
  def measureGetter(self, name):
    if name in self.measureMethods:
      def getter(object):
        measure = self.measureMethods[name](object)
        return measure.getID() if isinstance(measure, RegionalUnit) else measure
      return getter
    else:
      return self.dedicatedMeasurer.dedicatedMeasureGetter(name)    
  
  def outputMeasures(self, zone, row):
    for inName, outName in self.outputNames:
      row.setValue(outName, self.getMeasure(zone, inName))
    return row
  
  def createOutputFields(self, layer, sample, exclude=[]):
    for inName, outName in self.outputNames:
      if outName not in exclude:
        arcpy.AddField_management(layer, outName, common.pyTypeToOut(type(self.getMeasure(sample, inName))))
  
  def createOutputNameDict(self, names, regName=None):
    d = {}
    for name in names:
      if name in self.measureMethods:
        d[name] = name
      elif name in self.dedicatedMeasurer.measureMethods:
        d[name] = (regName + '_' if regName else '') + name
      else:
        raise KeyError, 'measure %s not found' % name
    return d
  
  # MEASUREMENT METHODS
  @staticmethod
  def maxOutflow(object):
    outflows = object.getOutflows()
    return (outflows.max() if outflows else 0)
    
  @staticmethod
  def coreOutflow(object):
    reg = object.getRegion()
    outflows = object.getOutflows()
    if reg and outflows:
      return (outflows.sumToRegion(reg) if object.getCore() else outflows.sumToCoreOf(reg))
    else:
      return 0
  
  @staticmethod
  def regOutflow(object):
    reg = object.getRegion()
    outflows = object.getOutflows()
    if reg and outflows:
      return outflows.sumToRegion(reg)
    else:
      return 0
  
  @staticmethod
  def outOutflow(object):
    reg = object.getRegion()
    outflows = object.getOutflows()
    if reg and outflows:
      return outflows.sumOutOf(reg)
    else:
      return 0

  @staticmethod
  def maxOutflowRatio(object):
    outflows = object.getOutflows()
    return (outflows.max() / float(outflows.sum()) if outflows else 0)
      
  @classmethod
  def coreOutflowRatio(cls, object):
    outflows = object.getOutflows()
    return (cls.coreOutflow(object) / float(outflows.sum()) if outflows else 0)

  @classmethod
  def regOutflowRatio(cls, object):
    outflows = object.getOutflows()
    return (cls.regOutflow(object) / float(outflows.sum()) if outflows else 0)

  @classmethod
  def outOutflowRatio(cls, object):
    outflows = object.getOutflows()
    return (cls.outOutflow(object) / float(outflows.sum()) if outflows else 0)

  @staticmethod
  def maxTarget(object):
    outflows = object.getOutflows()
    return (outflows.strongest() if outflows else None)
  
  @staticmethod
  def maxRegion(object):
    outflows = object.getOutflows()
    return (outflows.strongestRegional() if outflows else None)
  
  @staticmethod
  def maxHamplMembership(object):
    '''Returns the maximum Hampl membership function value for the object.'''
    return object.maxMembership(object.hamplMembership)
  
  @staticmethod
  def regHamplMembership(object):
    '''Returns Hampl membership value for the object in its region.'''
    return object.hamplMembership(object.getRegion(), penal=object.getPenalization())
  
  @staticmethod
  def regHamplMembershipMass(object):
    '''Returns Hampl membership mass for the object in its region.'''
    return object.hamplMembershipMass(object.getRegion(), object.getPenalization())
  
  @staticmethod
  def sumInflows(object):
    return object.sumFlows(out=False)

  @staticmethod
  def sumOutflows(object):
    return object.sumFlows(out=True)

  @staticmethod
  def sumCoreZoneInflows(object):
    print object.getInflows()
    print object.getInflows().toCore()
    print object.getInflows().toCore().restrictToRegions()
    return object.getInflows().toCore().restrictToRegions().sum()

  @staticmethod
  def sumCoreZoneOutflows(object):
    return object.getOutflows().toCore().restrictToRegions().sum()

  @staticmethod
  def exclaveFlag(object):
    return object.getExclaveFlag()

ZoneMeasurer.measureMethods = {'MAX_OUT' : ZoneMeasurer.maxOutflow, 'MAX_D' : ZoneMeasurer.maxTarget, 'CORE_OUT' : ZoneMeasurer.coreOutflow, 'REG_OUT' : ZoneMeasurer.regOutflow, 'NOREG_OUT' : ZoneMeasurer.outOutflow, 'NOREG_OUT_Q' : ZoneMeasurer.outOutflowRatio, 'MAX_MEM' : ZoneMeasurer.maxHamplMembership, 'REG_MEM' : ZoneMeasurer.regHamplMembership, 'MAX_OUT_Q' : ZoneMeasurer.maxOutflowRatio, 'CORE_OUT_Q' : ZoneMeasurer.coreOutflowRatio, 'REG_OUT_Q' : ZoneMeasurer.regOutflowRatio,   'REG_MASS' : ZoneMeasurer.regHamplMembershipMass, 'IS_EXC' : ZoneMeasurer.exclaveFlag, 'TOT_IN' : ZoneMeasurer.sumInflows, 'TOT_OUT' : ZoneMeasurer.sumOutflows, 'TOT_IN_CORE' : ZoneMeasurer.sumCoreZoneInflows, 'TOT_OUT_CORE' : ZoneMeasurer.sumCoreZoneOutflows}

      
class RegionMeasurer:
  def __init__(self):
    self.measures = {}
  
  def getMeasure(self, object, name):
    # common.message(name)
    # common.message(self.measureMethods.keys())
    if object not in self.measures:
      self.measures[object] = {}
    if name not in self.measures[object]:
      if name not in self.measureMethods:
        raise ValueError, 'measure %s not known' % name
      else:
        measure = self.measureMethods[name](object)
        self.measures[object][name] = (measure.getID() if isinstance(measure, RegionalUnit) else measure)
    return self.measures[object][name]
  
  def getDedicatedMeasure(self, object, name):
    return self.getMeasure(object.getRegion(), name)
  
  def dedicatedMeasureGetter(self, name):
    if name not in self.measureMethods:
      raise ValueError, 'measure %s not known' % name
    def getter(object):
      reg = object.getRegion()
      if reg not in self.measures:
        self.measures[reg] = {}
      if name not in self.measures[reg]:
        measure = self.measureMethods[name](reg)
        self.measures[reg][name] = (measure.getID() if isinstance(measure, RegionalUnit) else measure)
      return self.measures[reg][name]
    return getter
  
  # MEASUREMENT METHODS
  @classmethod
  def hamplRegionIntegrity(cls, object):
    outsum = object.getOutflows().sum()
    if outsum:
      return cls.coreHintMutualFlowSum(object) / float(outsum) # i1+i2/d1+d2
    else:
      return cls.coreHintMutualFlowSum(object)
  
  @staticmethod
  def hamplHinterlandIntegrity(object):
    outsum = object.getOutflows(core=False, hinter=True).sum()
    if outsum:
      return object.getHintCoreFlows().sum() / float(outsum) # i1/d1
    else:
      return object.getHintCoreFlows().sum()
  
  @staticmethod
  def hinterlandSignificance(object):
    return object.getHinterlandMass() / float(object.getMass())

  @staticmethod
  def bezakSelfContainment(object):
    return object.getIntraflows().sum() / float(object.getMutualFlows().sum())

  @staticmethod
  def coombesSelfContainment(object):
    return (self.residenceSelfContainment(object) + self.workplaceSelfContainment(object)) / 2.0

  # def bezakCrit(object):
    # return min(object.objectContainment(), 1) * min(1.0526 * object.getMass() / object.minMass, 1)
  
  # def coombesCrit(object):
    # return min(object.getMass() / object.minMass, 1) * (min(object.residenceSelfCont() / 0.8, 1) ** 2) * min(object.workplaceSelfCont() / 0.8, 1)

  @staticmethod
  def residenceSelfContainment(object):
    intra = object.getIntraflows().sum()
    return intra / float(intra + object.getOutflows().sum())
  
  @staticmethod
  def workplaceSelfContainment(object):
    intra = object.getIntraflows().sum()
    return intra / float(intra + object.getInflows().sum())
  
  @staticmethod
  def emw(object):
    return object.emw()
  
  @staticmethod
  def fmw(object):
    return object.fmw()
  
  @staticmethod
  def intraFlowSum(object):
    return object.getIntraflows().sum()
  
  @staticmethod
  def coreHintMutualFlowSum(object):
    return (object.getIntraflows(fromHinter=False, toCore=False).sum() + object.getIntraflows(toHinter=False, fromCore=False).sum())
  
  @staticmethod
  def outflowSum(object):
    return object.getOutflows().sum()
  
  @staticmethod
  def inflowSum(object):
    return object.getInflows().sum()
  
  @staticmethod
  def mutualFlowSum(object):
    return object.getMutualFlows().sum()
  
RegionMeasurer.measureMethods = {'HAM_IR' : RegionMeasurer.hamplRegionIntegrity, 'HAM_IZ' : RegionMeasurer.hamplHinterlandIntegrity, 'HAM_SIG' : RegionMeasurer.hinterlandSignificance, 'COO_SC' : RegionMeasurer.coombesSelfContainment, 'BEZ_SC' : RegionMeasurer.bezakSelfContainment, 'RB_SC' : RegionMeasurer.residenceSelfContainment, 'WB_SC' : RegionMeasurer.workplaceSelfContainment, 'FMW' : RegionMeasurer.fmw, 'EMW' : RegionMeasurer.emw, 'R_INTRA_SUM' : RegionMeasurer.intraFlowSum, 'R_C_H_SUM' : RegionMeasurer.coreHintMutualFlowSum, 'R_OUT_SUM' : RegionMeasurer.outflowSum, 'R_IN_SUM' : RegionMeasurer.inflowSum, 'R_BOTH_SUM' : RegionMeasurer.mutualFlowSum}
  