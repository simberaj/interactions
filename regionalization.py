import collections, operator
import common, colors, loaders, stats
from loaders import ConfigError
import objects
from objects import Region, Assignment

# TODO then:
# load requirements
# loader separation
# copying output parameters
# markov subbinding
# other todo features
# regional loader
# feng membership fuzzier
# decide whether to run output calculation based on output requirements

MASS_TO_STRG = 1e-10
ID_SORTER = operator.methodcaller('getID')
MASS_SORTER = operator.methodcaller('getMass')
SECONDARY_MASS_SORTER = operator.methodcaller('getSecondaryMass')
GAIN_SORTER = operator.methodcaller('getGain')

DEBUG_FLOW = True

class Regionalizer:
  def __init__(self, regionFactory):
    self.elements = {}
    self.stages = [] # sequential
    self.regionFactory = regionFactory
    self.regionOverlaps = {} # optional output
    self.initDone = False
  
  def addElements(self, elements):
    for id in elements:
      self.elements[id] = elements[id]
  
  def addStages(self, stages):
    for stage in stages:
      stage.reference(self.elements)
    self.stages += stages
    
  def neighbourhoodNeeded(self):
    for item in self.elements.itervalues():
      if (isinstance(item, Changer) or 
          (isinstance(item, Fuzzier) and item.hasExclavePenalization()) or 
          (isinstance(item, Destroyer) and item.targetsExclaves()) or 
          (isinstance(item, FlowAggregator) and item.hasNeighbourhoodCondition()) or
          isinstance(item, NeighbourhoodAggregator)):
        return True
    return False

  def initRun(self, zones, presets=[]):
    self.zones = zones
    self.zones.sort(key=ID_SORTER)
    common.progress('creating regions')
    self.regions = self.createRegions(self.zones)
    if presets:
      self.current = AlgorithmStage('applying presets', 0)
      self.current.reference([])
      self.applyPresets(presets)
    self.initDone = True
  
  def run(self, zones, presets=[]):
    if not self.initDone:
      self.initRun(zone, presets)
    if not self.stages:
      raise ConfigError, 'no algorithm stage specified, aborting'
    for stage in self.stages:
      self.current = stage
      self.current.run(self)
      self.regions = self.recreateRegions()
  
  def postRun(self):
    for stage in self.stages:
      if isinstance(stage, OutputStage):
        self.current = stage
        self.current.run(self)
        self.regions = self.recreateRegions()
  
  def createRegions(self, zones):
    regions = []
    for zone in zones: # region for each core zone
      if zone.coreable:
        regions.append(self.regionFactory(zone))
    regions.sort(key=ID_SORTER)
    return regions
  
  def applyPresets(self, presets):
    self.regions.sort(key=ID_SORTER)
    for preset in presets:
      zone = self.findBinaryByID(self.zones, preset.getZoneID())
      targetReg = self.findBinaryByID(self.regions, preset.getRegionID())
      if targetReg is None: # if the preset region is not valid
        common.warning('{id} is not an allowed region ID, assignment of zone {zone} to it failed'.format(id=preset.getRegionID(), zone=zone.getID()))
        zone.deassign()
      else:
        currentRegions = zone.getRegions()
        if currentRegions != [targetReg]: # current location is not desired
          zone.deassign()
          for reg in currentRegions:
            if not reg: # remove region if it became empty
              self.regions.remove(reg)
          if DEBUG_FLOW:
            state = 'core' if preset.getCoreState() else 'hinterland'
            common.debug('Zone {zone} preset: {targetReg} ({state})'.format(**locals()))
          self.current.tangleOne(Assignment(zone, targetReg, preset.getCoreState()))
        
  def recreateRegions(self):
    regset = set(zone.getRegion() for zone in self.zones)
    regset.discard(None)
    return sorted(regset, key=ID_SORTER)
  
  def getTargetsFor(self, element):
    if element.targetsRegions():
      return self.regions
    else:
      if element.targetsUnassigned():
        return [zone for zone in self.zones if not zone.isAssigned()]
      else:
        return self.zones
  
  def getZones(self):
    return self.zones
  
  def getOutputZones(self):
    outZones = {}
    for zone in self.zones:
      outZones[zone.getID()] = zone
    return outZones
    
  def getRegions(self):
    return self.regions
  
  def setRegionOverlaps(self, overlaps):
    self.regionOverlaps = overlaps

  def getRegionOverlaps(self):
    return self.regionOverlaps

  @staticmethod
  def findBinaryByID(cont, id):
    start = 0
    end = len(cont)
    while True:
      i = (start + end) / 2
      locID = cont[i].getID()
      if locID == id:
        return cont[i]
      elif locID < id:
        start = i
      else:
        end = i
      if start == end:
        return None
  
  def getRegionFactory(self):
    return self.regionFactory

class RegionalizationElement:
  def initElement(self, stage, ref):
    if ref:
      try:
        return getattr(stage, ref)
      except AttributeError:
        raise ConfigError, '{ref} not found for stage {stage}'.format(ref=ref, stage=stage.getNo())
    else:
      return self
  
  def setActive(self, active):
    self.active = active
  
  def isActive(self):
    return self.active

        
class SortingUser(RegionalizationElement):
  def __init__(self, sorterRef=None, secondaryRef=None):
    self.sorterRef = sorterRef
    self.secondaryRef = secondaryRef

  def join(self, stage):
    self.sorter = self.initElement(stage, self.sorterRef).createSorter()
    self.secondary = self.initElement(stage, self.secondaryRef).createSorter()
  
  def getSorter(self):
    return self.sorter
  
  def createSorter(self):
    return None

    
class Aggregator(SortingUser):
  targetsUnassigned = lambda self: True

  def __init__(self, target, descending, warnFail, **kwargs):
    SortingUser.__init__(self, **kwargs)
    self.isRegional = target
    self.descending = descending
    self.warnFail = warnFail
    self.failRow = 0
    self.finalRound = False

  def targetsRegions(self):
    return self.isRegional
  
  def feed(self, targets):
    # for target in targets:
      # print target.getAssignments()
    # print targets
    self.targets = targets
    self.targets.sort(key=operator.methodcaller('getRawMass'))
    self.todo = []

  def next(self):
    if not self.targets:
      if self.todo:
        # print self.todo, self.failRow, len(self.todo)
        if self.failRow >= len(self.todo):
          if self.finalRound:
            return None
          else:
            self.finalRound = True
        self.targets.extend(self.todo)
        self.todo = []
      else:
        return None
    self.sorter.sort(self.targets, reverse=(not self.descending))
    return self.targets.pop()
    
  def aggregate(self, candidate):
    ok = False
    for assignment in self.aggregateItem(candidate):
      if assignment is not None:
        ok = True
      yield assignment
    if ok:
      self.failRow = 0
    else:
      # print candidate
      self.failRow += 1
      self.todo.append(candidate)

  def fail(self):
    if self.todo and self.warnFail:
      common.warning('{name} {todos} could not be assigned ({reason})'.format(
        name=('Regions' if self.isRegional else 'Zones'),
        todos=', '.join(str(item.getID()) for item in self.todo),
        reason=self.getFailReason()))
  
  def createSorter(self):
    return AggregationSorter(self)
  
  def getSortFunction(self): # TODO: aggregation sorting
    return lambda x: x
    
class FlowAggregator(Aggregator):
  detailed = False
  
  def __init__(self, targetCoreOnly, bidirectional, tryChange, tryMerge, useHinterlandFlows, separateHinterland, neighcon, transform, indirectLinkage, **kwargs):
    Aggregator.__init__(self, **kwargs)
    self.targetCoreOnly = targetCoreOnly
    self.bidirectional = bidirectional
    self.tryChange = tryChange
    self.tryMerge = tryMerge
    self.useHinterlandFlows = useHinterlandFlows
    self.separateHinterland = separateHinterland
    self.neighcon = neighcon
    self.transform = transform
    self.indirectLinkage = indirectLinkage

  def doTryChange(self):
    return self.tryChange
  
  def doTryMerge(self):
    return self.tryMerge
  
  def hasNeighbourhoodCondition(self):
    return self.neighcon
    
  def aggregateItem(self, item):
    if self.targetsRegions():
      for assignment in self.aggregateRegion(item):
        yield assignment
    else:
      yield self.aggregateZone(item)
  
  def aggregateZone(self, zone):
    flows = self.indirectLinkage(self, zone, self.getFlowsForZone(zone))
    # print flows
    # if str(zone.getID()) == '576794':
      # common.debug(flows)
      # common.debug([tgt for tgt in flows.allOver(flows.max()).keys() if isinstance(tgt, Region)])
      # common.debug(self.secondary.max([tgt for tgt in flows.allOver(flows.max()).keys() if isinstance(tgt, Region)]))
    limitTo = (zone.getContiguousRegions() if self.finalRound and self.neighcon else None)
    target = self.getAggregationTarget(flows, limitTo)
    if target is None or self.neighcon and target not in zone.getContiguousRegions():
      if DEBUG_FLOW: common.debug('{zone} not assigned'.format(**locals()))
      return None
    else:
      if DEBUG_FLOW: common.debug('{zone}: {target}'.format(**locals()))
      return Assignment(zone, target, False)
  
  def aggregateRegion(self, region):
    # if region.getID() == '508004':
      # self.detailed = True
    flows = self.indirectLinkage(self, region, self.getFlowsForRegion(region))
    limitTo = (region.getContiguousRegions() if self.finalRound and self.neighcon else None)
    # if region.getID() == '508004':
      # common.debug(region, flows)
      # common.debug(region.getMutualFlows(hinter=self.useHinterlandFlows))
      # self.detailed = False
    target = self.getAggregationTarget(flows, limitTo)
    if self.neighcon and target not in region.getContiguousRegions():
      target = None
    if DEBUG_FLOW: common.debug('{region}: {target}'.format(**locals()))
    return self.assignmentsForRegion(region, target)
  
  def assignmentsForRegion(self, region, target):
    if target is None:
      yield None
    else:
      zones = region.getCoreZones() if self.separateHinterland else region.getZones()
      for zone in zones:
        yield Assignment(zone, target, False)
      region.erase()
      if self.separateHinterland:
        for zone in region.getHinterlandZones():
          yield self.aggregateZone(zone)
      
  def getAggregationTarget(self, flows, limitTo=None):
    if flows:
      # if limited to a set, remove all others
      if limitTo:
        flows.restrict(limitTo)
      # expects that at least one maximum is region (ensured by indirect linkage?)
      tops = [tgt for tgt in flows.allOver(flows.max()).keys() if isinstance(tgt, Region)]
      if tops:
        if len(tops) == 1:
          return tops[0]
        else:
          # print tops
          return self.secondary.max(tops)
      else: # otherwise... dunno
        return None
    else:
      return None # linking exhausted or simply no flows
  
  def getFlowsForZone(self, zone):
    flows = self.processFlows(zone.getOutflows(), out=True)
    if self.bidirectional:
      flows += self.processFlows(zone.getInflows(), out=False)
    return flows.exclude([zone])
  
  def getFlowsForRegion(self, region):
    # common.debug(region.getAssignments())
    # common.debug(region.getOutflows(hinter=self.useHinterlandFlows))
    # common.debug(region, region.getOutflows(hinter=self.useHinterlandFlows))
    # common.debug(region, region.getInflows(hinter=self.useHinterlandFlows))
    flows = self.processFlows(region.getOutflows(hinter=self.useHinterlandFlows, own=True), out=True)
    # common.debug(self.bidirectional)
    if self.bidirectional:
      flows += self.processFlows(region.getInflows(hinter=self.useHinterlandFlows, own=True), out=False)
    # common.debug(region, flows)
    return flows.exclude([region])
  
  def processFlows(self, flows, out):
    regional = flows.toCore() if self.targetCoreOnly else flows.toRegional()
    if self.transform:
      flowSum = float(regional.sum())
      for target in regional:
        if self.detailed:
          common.debug(target, regional[target], flowSum, self.flowSumFor(target, out), out)
        regional[target] = self.transform(regional[target], flowSum, self.flowSumFor(target, out))
    return regional
  
  def flowSumFor(self, target, out):
    if isinstance(target, Region):
      return (target.getInflows(hinter=self.useHinterlandFlows, own=True) if out else target.getOutflows(hinter=self.useHinterlandFlows, own=True)).sum()
    else:
      return (target.getInflows() if out else target.getOutflows()).sum()
  
  def getFailReason(self):
    return 'no flows{contig} found'.format(contig=(' to contiguous targets' if self.neighcon else ''))

  @staticmethod
  def intramaxTransform(flow, toSum, counterSum):
    try:
      return flow / (toSum * counterSum)
    except ZeroDivisionError:
      return 0

  @staticmethod
  def smartTransform(flow, toSum, counterSum):
    try:
      # common.debug(flow, toSum, counterSum)
      return flow ** 2 / (toSum * counterSum)
    except ZeroDivisionError:
      return 0

  @staticmethod
  def curdsTransform(flow, toSum, counterSum):
    try:
      return flow * (1 / toSum + 1 / float(counterSum))
    except ZeroDivisionError:
      return 0
  
  # @staticmethod
  # def absoluteTransform(newFlows, mainFlows, out=False, coef=1):
    # mainFlowSum = float(mainFlows.sum())
    # for target in mainFlows:
      # newFlows[target] += coef * mainFlows[target]
    # return newFlows

  # @staticmethod
  # def intramaxTransform(newFlows, mainFlows, out=False, coef=1):
    # mainFlowSum = float(mainFlows.sum())
    # for target in mainFlows:
      # newFlows[target] += coef * mainFlows[target] / (mainFlowSum + float(target.sumFlows(out)))
    # return newFlows

  # @staticmethod
  # def smartTransform(newFlows, mainFlows, out=False, coef=1):
    # mainFlowSum = float(mainFlows.sum())
    # for target in mainFlows:
      # newFlows[target] += coef * mainFlows[target] ** 2 / (mainFlowSum + float(target.sumFlows(out)))
    # return newFlows

  # @staticmethod
  # def curdsTransform(newFlows, mainFlows, out=False, coef=1):
    # ratioFactor = 1 / float(mainFlows.sum())
    # for target in mainFlows:
      # newFlows[target] += coef * mainFlows[target] * (ratioFactor + 1 / float(target.sumFlows(out)))
    # return newFlows
  
  def toRegions(self, object, flows):
    return flows.restrictToRegions()
  
  def gradeDown(self, object, flows):
    if flows:
      # common.debug(object)
      # common.debug(flows)
      sources = [object]
      i = 0
      maxTarget = common.maxKey(flows)
      while not isinstance(maxTarget, Region):
        sources.append(maxTarget)
        # common.debug(sources)
        # print flows, maxTarget, self.getFlowsForZone(maxTarget)
        flows += (self.getFlowsForZone(maxTarget) * (flows[maxTarget] / float(flows.sum())))
        flows.exclude(sources)
        if not flows:
          return flows
        maxTarget = common.maxKey(flows)
        i += 1
        # if i > 2:
          # raise RuntimeError
    return flows
  
  def markovChain(self, object, flows):
    return flows # TODO

class RingAggregator(Aggregator):
  def __init__(self, threshold, **kwargs):
    Aggregator.__init__(self, **kwargs)
    self.threshold = threshold

  def aggregateItem(self, item):
    if not item.isAssigned():
      flows = item.getOutflows()
      if flows and flows.max() / flows.sum() >= self.threshold:
        reg = common.maxKey(flows).getCore()
        if reg is not None:
          if DEBUG_FLOW: common.debug('Zone {item} in ring: {reg}'.format(**locals()))
          yield Assignment(item, reg, False)
  
  def getFailReason(self):
    return 'no flows over {threshold} % found'.format(threshold=self.threshold)
 
class NeighbourhoodAggregator(Aggregator):
  def aggregateItem(self, item):
    contigs = item.getContiguousRegions()
    if contigs:
      target = self.secondary.max(contigs)
      if DEBUG_FLOW: common.debug('{item} by neighbourhood: {target}'.format(**locals()))
      return [Assignment(item, target, False)]
    else:
      if DEBUG_FLOW: common.debug('{item} by neighbourhood not assigned'.format(**locals()))
      return [None]
  
  def getFailReason(self):
    return 'no assigned neighbours found'

 
class Changer(SortingUser):
  def __init__(self, threshold, protect=True, **kwargs):
    SortingUser.__init__(self, **kwargs)
    self.threshold = threshold
    self.protect = protect
  
  def isProtecting(self):
    return self.protect
  
  def enlarger(self, region):
    return Enlarger(self, region)
  
  def optimizer(self, regions):
    return Optimizer(self, regions)
  
  def getAllChanges(self, regions):
    '''Returns all possible changes between the specified regions.'''
    return list(self.getChangesToRegion(region) for region in regions)

  def getAffectedChanges(self, change, allRegs=[]):
    '''Returns all changes concerning regions that have been affected by change, limited to allRegs.'''
    if len(allRegs) == 1:
      return self.getChangesToRegion(change.getTargetRegion())
    else:
      affectedRegs = change.getAffectedRegions()
      # take the zone's change and consider all its inflows and neighbours
      return (self.getChangesToRegion(affectedRegs[0]) + 
        self.getChangesFromRegion(affectedRegs[1], affectedRegs[0]) + 
        self.getChangesToRegion(affectedRegs[1]) + 
        self.getChangesFromRegion(affectedRegs[0], affectedRegs[1]))
  
  def getChangesToRegion(self, region):
    '''Returns possible reassignments of border zones of region's neighbouring regions to it.'''
    changes = []
    if region is not None:
      for neigh in region.getContiguousZones():
        if not neigh.getCore(): # do not allow core reassignment  
          # if neigh.getRegion() is region:
            # common.warning('%s %s %s' % (neigh.assignments, region, neigh.assignments[0] in region.assignments))
          change = self.createChange(neigh, neigh.getRegion(), region)
          if self.viable(change):
            changes.append(change)
    return changes
  
  def getChangesFromRegion(self, region, notTo=None):
    '''Returns possible reassignments of border zones from region to its neighbouring regions.'''
    changes = []
    if region is not None:
      borderings = region.getHinterlandZoneBorderings()
      for zone in borderings:
        for tgtRegion in borderings[zone]:
          if tgtRegion is not notTo:
            change = self.createChange(zone, region, tgtRegion)
            if self.viable(change):
              changes.append(change)
    return changes
  
  def register(self, change):
    self.changesPerformed[change.getZone()] = change.getAffectedRegions()
  
  def hasBeenPerformed(self, change):
    return change.getAffectedRegions() not in self.changesPerformed[change.getZone()]
    
  def createChange(self, zone, fromReg, toReg):
    return HamplChange(zone, fromReg, toReg)

  def viable(self, change):
    '''Returns True (and therefore accepts the change as a good enough choice to be carried out) if there is a good relative gain and the zone has not been already changed between those regions.'''
    return self.hasChangeGain(change) and not self.hasBeenPerformed(change)
  
class AbsoluteChanger(Changer):
  # def isChangeSignificant(self, change):
    # '''Returns True if a flow from the zone to the target region is a significant flow for the zone.'''
    # return bool(change.getTargetRegion() in change.getZone().getOutflows().toCore().significant())
  
  def hasChangeGain(self, change):
    '''Returns True if the change's gain is large enough compared to the current minimum threshold.'''
    return (change.absGain() > self.threshold)
  
class RelativeChanger(Changer):
  def hasChangeGain(self, change):
    '''Returns True if the change's gain is large enough compared to the current minimum threshold.'''
    return (change.relGain() > self.threshold)
  
class ChangeGenerator:
  def __init__(self, changer):
    self.changer = changer
    self.sorter = self.changer.getSorter()
    self.accepted = []
    self._update()

  def accept(self, change):
    self.changer.register(change)
    self.accepted.append(change)
    self._update(change)

  def next(self):
    return self.changes.pop()
    
class Enlarger(ChangeGenerator):
  def __init__(self, changer, region):
    self.region = region
    ChangeGenerator.__init__(changer)
  
  def _update(self, change=None):
    self.changes = self.changer.getChangesToRegion(self.region)
    self.sorter.sort(self.changes)
  
  def rollback(self):
    return [change.makeRollbackAssignment() for change in self.accepted]
  
class Optimizer(ChangeGenerator):
  def __init__(self, changer, regions):
    self.regions = regions
    ChangeGenerator.__init__(changer)
  
  def _update(self, change=None):
    if change is None:
      self.changes = self.changer.getAllChanges()
    else:
      self._removeAffected(change)
      self.changes += self.changer.getAffectedChanges(change)
      self.sorter.sort(self.changes) 
  
  def _removeAffected(self, change):
    affected = change.getAffectedRegions()
    while i < len(self.changes):
      if self.changes[i].isAffected(nowAffected):
        self.changes.pop(i)
      else:
        i += 1

        
class Change:
  '''An attempt to change the assignment of a zone from the source region to the target region.'''
  
  def __init__(self, zone, source, target):
    self.zone = zone
    self.source = source
    self.target = target
    self._gainCalc = False
  
  def getZone(self):
    return self.zone
  
  def getSource(self):
    return self.source
  
  def getTarget(self):
    return self.target
  
  def _calcGain(self):
    '''Calculates the overall system EMW gain resulting from the change.
    Called only when the situation has changed.'''
    if self.source is None:
      self.fromLoss = 0
    else:
      self.fromLoss = self.getDiff(self.source, self.zone)
    self.toGain = self.getDiff(self.target, self.zone)
    self.gain = self.toGain - self.fromLoss
    self._gainCalc = True
  
  def assignment(self):
    '''Prepares the zone to be assigned to the target region and returns that assignment.'''
    if DEBUG_FLOW: common.debug('Change %s' % self)
    self.zone.deassign()
    return Assignment(self.zone, self.target, core=False)
  
  def rollback(self):
    '''Prepares the zone to be assigned back to the source region (rollback the change) and returns that assignment.'''
    if DEBUG_FLOW: common.debug('Rollback change %s' % self)
    self.zone.deassign()
    return Assignment(self.zone, self.source, core=False)
    
  def absGain(self):
    if not self._gainCalc:
      self._calcGain()
    return self.gain
  
  def relGain(self):
    '''Returns the change gain divided by the zone's mass.'''
    return self.getGain() / float(self.zone.getMass())

  def getAffected(self):
    '''Returns a tuple with the source and target region.'''
    return (self.source, self.target)
  
  def isAffected(self, byRegs):
    '''Returns if the change is affected by changes in some of the regions in byRegs.'''
    return (self.source in byRegs or self.target in byRegs)
    
  def __repr__(self):
    return '<%s (%s) -> %s (%s; %s - %s; %s)' % (self.zone, self.zone.getAssignments(), self.target, self.getGain(), self.toGain, self.fromLoss, self.getRelativeGain())

class HamplChange(Change): # TODO: other differences than fuzzy mass (SC and so on...)
  def getDiff(self, region, zone):
    return region.getEMWDiff(zone)
  
    
class Fuzzier(RegionalizationElement): # TODO: oscillation
  def __init__(self, contiguity):
    self.contiguity = contiguity
    self._haspenal = (self.contiguity != 1)
  
  def hasExclavePenalization(self):
    return self._haspenal

  def _fuzzify(self, assignment):
    if self._haspenal and assignment.isExclave():
      if self.contiguity == 0: 
        assignment.setDegree(0)
      else:
        assignment.setDegree(self.contiguity * self.membership(assignment))
    else:
      assignment.setDegree(self.membership(assignment))
      
  def getMembershipFunctionName(self):
    return self.MEMBERSHIP_NAME

  def update(self, region):
    if self._haspenal:
      region.detectExclaves()
    for ass in region.getAssignments():
      self._fuzzify(ass)
    region.updateMass()

  def updateAll(self, regions):
    '''Updates assignment degrees (membership functions) of the assignments to the regions provided.'''
    for region in regions:
      if region is not None:
        self.update(region)
  
  def updateByChange(self, change):
    self.update(change.getSource())
    self.update(change.getTarget())
      
class BasicFuzzier(Fuzzier):
  def membership(self, assignment):
    return 1
  
  def foreignMembership(self, zone, region):
    return 0
  
  def membershipDifference(self, assignment, diffTarget):
    return 0
  
  def membershipDict(self, zone):
    return [(zone.getRegionColor(), 1)]

class HamplFuzzier(Fuzzier):
  def __init__(self, oscillation, **kwargs):
    Fuzzier.__init__(self, **kwargs)
    self.oscillation = oscillation

  def membership(self, assignment):
    if assignment:
      flows = assignment.getZone().getMutualFlows()
      if not flows:
        return 0
      region = assignment.getRegion()
      if assignment.isCore():
        iR, dR = flows.sumsByRegion(region)
      else: # intra-hinterland flows do not count
        iR, dR = flows.sumsByCore(region)
      try:
        return iR / (iR + dR)
      except ZeroDivisionError:
        return 0
    else:
      return 0
  
  def foreignMembership(self, zone, region):
    flows = zone.getMutualFlows()
    if flows:
      iR, dR = flows.sumsByCore(region)
      try:
        return iR / float(iR + dR)
      except ZeroDivisionError:
        return 0
    else:
      return 0
  
  def membershipDifference(self, assignment, diffTarget):
    if assignment:
      zone = assignment.getZone()
      flows = zone.getMutualFlows()
      if flows:
        if assignment.isCore():
          if diffTarget in flows:
            try:
              return flows[diffTarget] / float(flows.sumsByRegion(assignment.getRegion())) # TODO
            except ZeroDivisionError:
              return 0
          else:
            return 0
        elif diffTarget is zone:
          return 0
        else:
          if diffTarget in flows: # if any interaction relation at all
            toZone = flows[diffTarget] # d
          elif self._haspenal: # if possible neighbourhood difference
            toZone = 0
          else:
            return 0
          # get neighbourhood difference
          penal = self.penalization if (self._haspenal and diffTarget in zone.getNeighbours() and assignment.isOnlyConnection(diffTarget)) else 1 # e # TODO isOnly
          if penal == 1 and toZone == 0:
            return 0
          region = assignment.getRegion()
          toCore, outOfRegion = flows.sumsByCore(region) # c, o
          partsum = float(toCore + outOfRegion - (0 if diffZone.isInRegion(region) else toZone))
          try:
            return toCore * (1 / partsum - penal / (partsum + toZone))
          except ZeroDivisionError:
            return 0
      else:
        return 0
    else:
      return 0
  
  def membershipDict(self, zone):
    flows = zone.getMutualFlows()
    regflows = flows.toRegional()
    sum = float(flows.sum())
    memberships = []
    if zone.getCore():
      for item in regflows:
        if isinstance(item, Region):
          memberships.append((item.getColor(), regflows[item] / sum))
    else:
      coreflows = flows.toCore()
      for item in coreflows:
        if isinstance(item, Region):
          memberships.append((item.getColor(), coreflows[item] / (sum - regflows[item] + coreflows[item])))
    # common.debug(zone)
    # common.debug(flows)
    # common.debug(coreflows)
    # common.debug(regflows)
    # common.debug(memberships)
    return memberships

class SimberaFuzzier(Fuzzier): # TODO: diff
  def membership(self, assignment):
    flows = assignment.getZone().getMutualFlows()
    if not flows:
      return 0
    iR = flows.sumToRegion(assignment.getRegion())
    return iR / float(flows.sum())
  
  def foreignMembership(self, zone, region):
    flows = zone.getMutualFlows()
    if not flows:
      return 0
    iR = flows.sumToRegion(region)
    return iR / float(flows.sum())
  
  def membershipDifference(self, assignment, diffTarget):
    return 0 # TODO
  
  def membershipDict(self, zone):
    regflows = zone.getMutualFlows().toRegional()
    sum = float(regflows.sum())
    memberships = []
    for item in regflows:
      if isinstance(item, Region):
        memberships.append((item.getColor(), regflows[item] / sum))
    return memberships
    
class FengFuzzier(Fuzzier): # TODO: diff, foreign...
  def membership(self, assignment):
    flows = assignment.getZone().getMutualFlows()
    region = assignment.getRegion()
    if assignment.isCore():
      iR, dR = flows.sumsByRegion(region)
    else: # intra-hinterland flows do not count
      iR, dR = flows.sumsByCore(region)
    try:
      return iR / (iR + dR)
    except ZeroDivisionError:
      return 0
    
  def membershipDifference(self, assignment, diffTarget):
    return 0 # TODO
  
  
class Halter(RegionalizationElement): # OK
  pass

class CountHalter(Halter):
  def __init__(self, threshold):
    self.threshold = threshold
  
  def halt(self, targets):
    return len(targets) <= self.threshold

  
class Merger(SortingUser): # OK, multiready
  def __init__(self, target, threshold, neighcon, **kwargs):
    SortingUser.__init__(self, **kwargs)
    self.isRegional = target
    self.threshold = threshold
    self.neighcon = neighcon

  def join(self, stage):
    SortingUser.join(self, stage)
    self.fuzzier = self.initElement(stage, 'fuzzier')
  
  def targetsRegions(self):
    return self.isRegional

  def run(self, merged):
    if self.sorter:
      self.sorter.sort(merged)
    for region in merged:
      batch = self.single(region)
      if batch:
        merged.remove(region)
      yield batch
  
  def single(self, region):
    target = self.getTarget(region)
    if target:
      return self.merge(target, region) # merges region to target
    else:
      return None
  
  def merge(self, master, slave):
    if DEBUG_FLOW: common.debug('Merging {slave}: {master}'.format(**locals()))
    assig = []
    for core in slave.getCoreZones():
      core.deassign()
      assig.append(Assignment(core, master, core=True))
    for hinter in slave.getHinterlandZones():
      hinter.deassign()
      assig.append(Assignment(hinter, master, core=False))
    slave.erase()
    return assig
  

class HamplMerger(Merger): # TODO - length
  # def getTarget(self, region):
    # flows = region.getMutualFlows(hinter=self.isRegional)
    # targets = flows.sortedTargets()
    # for target in targets:
      # if flows[target] 
  pass
  
class OverlapMerger(Merger):
  def getTarget(self, region):
    candidates = {}
    for neigh in region.getContiguousRegions():
      overlap = self.overlap(region, neigh)
      # common.debug('%s %s overlap: %s x %s' % (region, neigh, overlap, self.overlapThreshold))
      if overlap > self.threshold:
        candidates[neigh] = overlap
    if candidates:
      return common.maxKey(candidates)
    else:
      return None

  def absoluteOverlap(self, region1, region2):
    return (sum(zone.getMass() * self.fuzzier.foreignMembership(zone, region2) for zone in region1.getZones()) + sum(zone.getMass() * self.fuzzier.foreignMembership(zone, region1) for zone in region2.getZones()))
  
class WattsMerger(OverlapMerger): # TODO      
  def overlap(self, region1, region2):
    # print region1, region2, sum(zone.getMass() * self.fuzzier.foreignMembership(zone, region2) for zone in region1.getZones()), sum(zone.getMass() * self.fuzzier.foreignMembership(zone, region1) for zone in region2.getZones()), region1.getMass(), region2.getMass()
    absover = self.absoluteOverlap(region1, region2)
    if absover > 0:
      return (absover / float(region1.getMass() + region2.getMass()))
    else:
      return 0.0

class MinimalMerger(OverlapMerger):
  def overlap(self, region1, region2):
    absover = self.absoluteOverlap(region1, region2)
    if absover > 0:
      return (absover / 2.0 / min(region1.getMass(), region2.getMass()))
    else:
      return 0.0
  

class CoombesMerger(Merger):
  def __init__(self, toFlowRatio, counterFlowRatio, **kwargs):
    Merger.__init__(self, **kwargs)
    self.toFlowRatio = toFlowRatio
    self.counterFlowRatio = counterFlowRatio
  
  def getTarget(self, region): # TODO: distinction of region/core targetting
    # print region
    inflows = region.getInflows(hinter=self.isRegional).toRegional().restrictToRegions()
    outflows = region.getOutflows(hinter=self.isRegional).toRegional().restrictToRegions()
    if not outflows:
      return None
    candidates = {}
    over = (outflows / outflows.sum()).allOver(self.toFlowRatio)
    for target in over:
      counterSum = target.getOutflows(hinter=self.isRegional).toRegional().restrictToRegions().sum()
      # print target, inflows[target] / counterSum, over[target], target.getOutflows(hinter=self.isRegional).sum(), target.getInflows(hinter=self.isRegional).sum()
      if inflows[target] and inflows[target] / counterSum >= self.counterFlowRatio:
        crit = inflows[target] ** 2 / (inflows.sum() * counterSum) + outflows[target] ** 2 / (outflows.sum() * target.getInflows(hinter=self.isRegional).toRegional().restrictToRegions().sum())
        if crit >= self.threshold:
          candidates[target] = crit
    if candidates:
      return common.maxKey(candidates)
      # if len(candidates) == 1 or not self.secondary: # TODO: some other way?
        # return candidates[0]
      # else:
        # return self.secondary.max(candidates)
    else:
      return None

  
class Destroyer(RegionalizationElement): # OK, multiready
  targetsUnassigned = lambda self: False

  def __init__(self, target, threshold, exclave):
    self.isRegional = target
    self.threshold = threshold
    self.exclave = exclave
  
  def targetsRegions(self):
    return self.isRegional
  
  def targetsExclaves(self):
    return self.exclave
  
  def run(self, targets):
    # print self.threshold, self.exclave
    for target in targets:
      # if target.isExclave():
        # print target, self.getCriterionValue(target), target.isExclave()
      if ((self.threshold and self.getCriterionValue(target) <= self.threshold) or
        (self.exclave and target.isExclave())):
        if DEBUG_FLOW: common.debug('Destroying %s' % target)
        if self.isRegional:
          target.erase()
        else:
          target.deassign()
    
class MembershipDestroyer(Destroyer):
  @staticmethod
  def getCriterionValue(target):
    return sum(ass.getDegree() for ass in target.getAssignments())

    
class Verifier(RegionalizationElement):
  pass
    
class VerificationGroup(Verifier): # OK
  def __init__(self, criteria):
    self.criteria = criteria

  def initThreshold(self, objects):
    for crit in self.criteria:
      crit.initThreshold(objects)
  
  def createSorter(self):
    sorters = set(crit.createSorter() for crit in self.criteria)
    if len(sorters) == 1:
      return sorters.pop()
    else:
      return MultipleSorter(sorters) # TODO: implement sorting priority...

class SimultaneousGroup(VerificationGroup):
  def verify(self, object):
    for crit in self.criteria:
      if not crit.verify(object):
        return False
    return True

  def verifyTimes(self, object, times):
    for crit in self.criteria:
      if not crit.verifyTimes(object, times):
        return False
    return True
    
  def verifyWithout(self, object, part):
    for crit in self.criteria:
      if not crit.verifyWithout(object, part):
        return False
    return True
    
  def verifyTogether(self, objects):
    for crit in self.criteria:
      if not crit.verifyTogether(objects):
        return False
    return True

class AlternativeGroup(VerificationGroup):
  pass # TODO

class LinearTradeoffGroup(VerificationGroup): # TODO
  pass

class VerificationCriterion(Verifier):
  sortfunction = None

  def __init__(self, min, value):
    self.min = min
    self.value = value
  
  def initThreshold(self, objects):
    if self.value is None:
      self.value = stats.genMode([self.getCriterionValue(obj) for obj in objects])
    
  def verify(self, object):
    verif = self.getCriterionValue(object)
    common.debug('verif: {} -> {} x {}'.format(object, verif, self.value))
    return (verif >= self.value) if self.min else (verif <= self.value)
  
  def verifyTimes(self, object, times):
    verif = self.getCriterionValue(object) * times
    return (verif >= self.value) if self.min else (verif <= self.value)
  
  def verifyWithout(self, object, part):
    verif = self.getCriterionValue(object) - self.getCriterionValue(part)
    return (verif >= self.value) if self.min else (verif <= self.value)
  
  def verifyTogether(self, objects):
    verif = sum(self.getCriterionValue(object) for object in objects)
    return (verif >= self.value) if self.min else (verif <= self.value)
  
  def createSorter(self):
    return VerificationSorter(self)
  
  def getSortFunction(self):
    return self.sortfunction


class MainMassCriterion(VerificationCriterion):
  sortfunction = MASS_SORTER
  ratio = False
  
  @staticmethod
  def getCriterionValue(object):
    return object.getMass()

class HinterlandMassCriterion(VerificationCriterion):
  sortfunction = MASS_SORTER
  ratio = False
  
  @staticmethod
  def getCriterionValue(object):
    return object.getHinterlandMass()

class SecondaryMassCriterion(VerificationCriterion):
  sortfunction = SECONDARY_MASS_SORTER
  ratio = False
  
  @staticmethod
  def getCriterionValue(object):
    return object.getSecondaryMass()

class MinimalSelfContainmentCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    return min(InflowSelfContainmentCriterion.getCriterionValue(object), OutflowSelfContainmentCriterion.getCriterionValue(object))
  
  sortfunction = getCriterionValue

class RatioSelfContainmentCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    try:
      return object.getIntraflows().sum() / float(object.getMutualFlows().sum())
    except ZeroDivisionError:
      return 0
  
  sortfunction = getCriterionValue

class OutflowSelfContainmentCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    intra = object.getIntraflows().sum()
    outfl = object.getOutflows().sum()
    try:
      return intra / float(intra + outfl)
    except ZeroDivisionError:
      return 0

  sortfunction = getCriterionValue

class InflowSelfContainmentCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    intra = object.getIntraflows().sum()
    infl = object.getInflows().sum()
    try:
      return intra / float(intra + infl)
    except ZeroDivisionError:
      return 0
  
  sortfunction = getCriterionValue

class AveragedSelfContainmentCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    intra = object.getIntraflows().sum()
    infl = object.getInflows().sum()
    outfl = object.getOutflows().sum()
    try:
      return 0.5 * intra * (1 / float(intra + infl) + 1 / float(intra + outfl))
    except ZeroDivisionError:
      return 0

  sortfunction = getCriterionValue
    
class RegionIntegrityCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    try:
      return (object.getIntraflows(fromHinter=False, toCore=False).sum() + object.getIntraflows(toHinter=False, fromCore=False).sum()) / float(object.getOutflows().sum())
    except ZeroDivisionError:
      return 0

  sortfunction = getCriterionValue
  
class HinterlandIntegrityCriterion(VerificationCriterion):
  ratio = True
  
  @staticmethod
  def getCriterionValue(object):
    try:
      return object.getIntraflows(toHinter=False, fromCore=False).sum() / float(object.getOutflows(core=False).sum())
    except ZeroDivisionError:
      return 0
  
  sortfunction = getCriterionValue

    
class OutputElement(RegionalizationElement):
  pass

class ZoneColoring(OutputElement):
  def __init__(self, mixer):
    self.mixer = mixer

  def join(self, stage):
    self.fuzzier = self.initElement(stage, 'fuzzier')
   
  def run(self, zones):
    for zone in zones:
      memdict = self.fuzzier.membershipDict(zone)
      if memdict:
        zone.setColor(self.mixer(memdict))
      else:
        zone.setColor(colors.BLACK_RGB)

  def getColorMixer(self):
    if self.mixerName:
      try:
        return colors.COLOR_MIXERS[self.mixerName]
      except KeyError:
        raise ConfigError, '{} color mixer not found'.format(self.mixerName)
    else:
      return None
    
    
class RegionOverlapping(OutputElement):
  def __init__(self):
    pass # not anything, really?
  
  def join(self, stage):
    self.merger = self.initElement(stage, 'merger')

  def run(self, regions):
    overlaps = {}
    for region in regions:
      overlaps[region] = {}
      for neigh in region.getContiguousRegions():
        if neigh not in overlaps:
          overlaps[region][neigh] = self.merger.overlap(region, neigh)
      if overlaps[region] == {}:
        del overlaps[region]
    print overlaps
    return overlaps

    
class BaseStage:
  ELEMENT_TYPES = ('fuzzier', 'verifier', 'merger')

  def __init__(self, message, no):
    self.no = no
    self.message = message
    self.itemrefs = {}

  def getNo(self):
    return self.no
  
  def addItems(self, items):
    for item in items:
      tag = item.getTag()
      if tag not in self.itemrefs:
        self.itemrefs[tag] = item
  
  def reference(self, elements):
    for elName in self.ELEMENT_TYPES:
      if elName in self.itemrefs:
        elID = self.itemrefs[elName].getID()
        try:
          item = elements[elID]
        except KeyError:
          raise ConfigError, '{} {} for stage {} not found but referenced'.format(elID, elName, self.no)
      else:
        item = None
      setattr(self, elName, item)
    for elName in self.ELEMENT_TYPES:
      item = getattr(self, elName)
      if hasattr(item, 'join'):
        item.join(self) # init sorters
    self._doVerify = self.verifier and self.verifier.isActive()

  def run(self, regionalizer):
    common.progress(self.message)
    if self.fuzzier and self.fuzzier.isActive():
      self.fuzzier.updateAll(regionalizer.getRegions())
    if self.verifier and self.verifier.isActive():
      self.verifier.initThreshold(regionalizer.getRegions())
  
    
class AlgorithmStage(BaseStage):
  ELEMENT_TYPES = BaseStage.ELEMENT_TYPES + ('aggregator', 'changer', 'halter', 'destroyer')

  def run(self, regionalizer):
    BaseStage.run(self, regionalizer)
    if self.aggregator:
      self.runAggregation(regionalizer.getTargetsFor(self.aggregator))
    elif self.merger:
      self.runMerge(regionalizer.getRegions())
    elif self.changer:
      self.runChange(regionalizer)
    elif self.destroyer:
      self.runDestroying(regionalizer.getTargetsFor(self.destroyer))
  
  def runAggregation(self, targets):
    self.aggregator.feed(targets)
    candidate = self.aggregator.next()
    while candidate:
      if self.halter and self.halter.halt(targets):
        break
      if self.isAggregable(candidate):
        if DEBUG_FLOW: common.debug('{} aggregating'.format(candidate))
        if self.changer and self.aggregator.doTryChange() and self.tryEnlarge(candidate):
          continue
        if self.merger and self.aggregator.doTryMerge() and self.tryMerge(candidate):
          continue
        created = self.aggregator.aggregate(candidate)
        if created:
          self.tangleMoreRegions(created)
      else:
        if DEBUG_FLOW: common.debug('{} not aggregable'.format(candidate))
      candidate = self.aggregator.next()
    if not self.halter:
      self.aggregator.fail()
        
  def tangleOne(self, assignment):
    assignment.tangle()
    if self.fuzzier: self.fuzzier.update(assignment.getRegion())
  
  def tangleRegion(self, listed):
    reg = None
    for assignment in listed:
      if reg is None:
        reg = assignment.getRegion()
      assignment.tangle()
    if reg and self.fuzzier:
      self.fuzzier.update(reg)
        
  def tangleMoreRegions(self, generator):
    regs = set()
    for assignment in generator:
      if assignment is not None:
        assignment.tangle()
        regs.add(assignment.getRegion())
    if self.fuzzier: self.fuzzier.updateAll(regs)
        
  def runMerge(self, targets):
    nowReg = None
    for batch in self.merger.run(targets):
      if batch:
        self.tangleRegion(batch)

  def runChange(self, regions):
    protect = self.changer.isProtecting()
    generator = self.changer.optimizer(regions)
    change = generator.next()
    while change:
      change.assignment().tangle()
      if self.fuzzier: self.fuzzier.updateByChange(change)
      if protect and not self.verifier.verify(change.getSource()):
        change.rollback().tangle()
        if self.fuzzier: self.fuzzier.updateByChange(change)
      else:
        generator.accept(change)
      change = generator.next()
  
  def tryMerge(self, region):
    if self.merger.targetsRegions():
      batch = self.merger.single(region)
      if batch:
        self.tangleRegion(batch)
      return bool(batch)
  
  def tryEnlarge(self, region):
    generator = self.changer.enlarger(region)
    change = generator.next()
    while change:
      change.assignment().tangle()
      if self.fuzzier: self.fuzzier.updateByChange(change)
      generator.accept(change)
      if self.verifier.verify(region):
        break
      change = next(generator)
    if self.isAggregable(region):
      self.tangleMoreRegions(generator.rollback())
      return False
    else:
      return True
      
  def runDestroying(self, targets):
    return self.destroyer.run(targets)
    
  def halt(self, targets):
    return not (halter and self.halter.halt(targets))
  
  def isAggregable(self, item):
    return not (self._doVerify and self.verifier.verify(item))
  

class OutputStage(BaseStage):
  ELEMENT_TYPES = BaseStage.ELEMENT_TYPES + ('coloring', 'overlap')

  def run(self, regionalizer):
    BaseStage.run(self, regionalizer)
    if self.coloring:
      self.coloring.run(regionalizer.getZones())
    if self.overlap:
      regionalizer.setRegionOverlaps(self.overlap.run(regionalizer.getRegions()))
  
  
class ElementReference:
  def __init__(self, tag, id):
    self.tag = tag
    self.id = id
  
  def getTag(self):
    return self.tag
  
  def getID(self):
    return self.id
  
  def __repr__(self):
    return '<{tag} {id}>'.format(tag=self.tag.capitalize(), id=self.id.upper())
      
class Sorter:
  def __init__(self, function):
    self.function = function
    self.catalog = {}
    self.masses = collections.defaultdict(lambda: -1)
    
  def sort(self, objects, **kwargs):
    for obj in objects:
      mass = obj.getMass()
      if self.masses[obj] != mass:
        self.catalog[obj] = self.function(obj)
        self.masses[obj] = mass
    objects.sort(key=self.catalog.get, **kwargs)
  
  def max(self, objects, **kwargs):
    return max(objects, key=self.function, **kwargs)
  
  def getFunction(self):
    return self.function

class SimpleSorter(Sorter):
  def __init__(self, element):
    Sorter.__init__(self, element.getSortFunction())
    
class AggregationSorter(SimpleSorter):
  pass

class VerificationSorter(SimpleSorter):
  pass
  
class MultipleSorter(Sorter):
  def __init__(self, sorters):
    Sorter.__init__(self, self.multiplyFunctionBuilder([sorter.getFunction() for sorter in sorters]))
  
  def multiplyFunctionBuilder(self, fxs):
    def multiplyFunction(x):
      return reduce(operator.mul, ((1e-4 if val == 0 else val) for val in (fx(x) for fx in fxs)))
    return multiplyFunction
  
class SetupReader(loaders.ConfigReader):
  CONTENT = 'file'

  def baseread(self, file):
    self.dom = self.parseFile(file)
    self.informName()
    self.parameters = self.parseParameters(self.dom)
  
  def informName(self):
    metael = self.dom.find('metadata')
    if metael is None:
      common.message('{} metainformation not found'.format(self.CONTENT.capitalize()))
    else:
      nameel = metael.find('name')
      if nameel is None:
        common.message('{} metainformation incomplete: name not found'.format(self.CONTENT.capitalize()))
      else:
        common.message('Using {what}: {name}'.format(what=self.CONTENT, name=nameel.text))
        
        
class RLSetupReader(SetupReader):
  VERSION = '1.1.0'
  ROOT_TAG_NAME = 'delimiterdata'
  CONTENT = 'data setup'
  rootPath = ''

  def __init__(self, parameters):
    SetupReader.__init__(self, parameters)
    self.PATH_FACTORIES = {'absolute' : (lambda path, base: path), 'relative' : (lambda path, base: os.path.join(base, path))}

  def create(self, file):
    self.baseread(file)
    self.rootPath = self.parsePath(self.dom.find('root-path'), base=os.path.dirname(file), require=False)
    loader = loaders.RegionalLoader()
    zoneel = self.dom.find('zones')
    loader.sourceOfZones(**self.parseLayerSetup(zoneel, name='zone'))
    loader.sourceOfPresets(self.parseSlots(zoneel.find('presets')))
    loader.possibleNeighbourhood(**self.parseLayerSetup(zoneel.find('neighbourhood'), require=False))
    loader.sourceOfInteractions(**self.parseLayerSetup(self.dom.find('interactions'), name='interaction', require=False))
    return loader
  
  def parseLayerSetup(self, elem, name, require=True):
    if not elem:
      raise ConfigError, name + ' setup not provided'
    path = self.parsePath(elem.find('path'), name=name, require=True)
    slots = self.parseSlots(elem.find('fields'), require=True)
    queryEl = elem.find('query')
    return {'layer' : path, 'slots' : slots, 'where' : ('' if queryEl is None else self.strGet(queryEl))}
    
  def parsePath(self, elem, base=None, require=False, name='', default=''):
    if elem is None:
      if require:
        raise ConfigError, '{} path not provided'.format(name)
      else:
        return default
    else:
      return self.typeGet(elem, self.PATH_FACTORIES)(self.strGet(elem), base=(self.rootPath if base is None else base))
  
  def parseSlots(self, elem, require=False, name='', default=None):
    if elem is None:
      if require:
        raise ConfigError, '{} field names not provided'.format(name)
      else:
        return {} if default is None else default
    else:
      slots = {}
      for fieldEl in elem.findall('field'):
        slots[self.strGet(fieldEl, 'slot')] = self.strGet(fieldEl, 'name')
      return slots
    
class DRSetupReader(SetupReader):
  VERSION = '1.1.0'
  FILE_PURPOSE = 'regionalization'
  ROOT_TAG_NAME = 'delimitersetup'
  CONTENT = 'algorithm'
  
  CRITERIA = {'mass' : MainMassCriterion,
    'secondary-mass' : SecondaryMassCriterion,
    'hinterland-mass' : HinterlandMassCriterion,
    'minimal-self-containment' : MinimalSelfContainmentCriterion, 
    'ratio-self-containment' : RatioSelfContainmentCriterion,
    'outflow-self-containment' : OutflowSelfContainmentCriterion, 
    'inflow-self-containment' : InflowSelfContainmentCriterion, 
    'averaged-self-containment' : AveragedSelfContainmentCriterion}
  AGGREGATION_TRANSFORMS = {'none' : None,
    'intramax' : FlowAggregator.intramaxTransform,
    'smart' : FlowAggregator.smartTransform,
    'curds' : FlowAggregator.curdsTransform}
  AGGREGATION_SUBBINDS = {'none' : FlowAggregator.toRegions,
    'gradual' : FlowAggregator.gradeDown,
    'markov' : FlowAggregator.markovChain}
  OBJECT_TARGETS = {'zone' : False, 'region' : True}
  PART_TARGETS = {'core' : False, 'region' : True}
  THRESHOLD_DIRECTIONS = {'min' : True, 'max' : False}
  # THRESHOLD_TYPES = {'fixed' : FixedThreshold, 'lower-bound' : FixedThreshold,'tradeoff-end' : TradeoffEnd}
  SORTERS = {'aggregation' : AggregationSorter, 'verification' : VerificationSorter}
  REGION_FACTORIES = {'static' : objects.StaticRegion, 'functional' : objects.FunctionalRegion}

  def __init__(self, parameters=tuple()):
    SetupReader.__init__(self, parameters)
    self.AGGREGATOR_FACTORIES = {'flow' : self.parseFlowAggregator, 'neighbourhood' : self.parseNeighbourhoodAggregator, 'ring' : self.parseRingAggregator}
    self.CHANGER_FACTORIES = {'relative' : self.parseRelativeChanger}
    self.FUZZIER_FACTORIES = {'basic' : self.parseBasicFuzzier, 'default' : self.parseBasicFuzzier, 'hampl' : self.parseHamplFuzzier, 'simbera' : self.parseSimberaFuzzier}
    self.DEFAULT_FUZZIER_FACTORY = self.parseBasicFuzzier
    self.HALTER_FACTORIES = {'count' : self.parseCountHalter}
    self.MERGER_FACTORIES = {'hampl' : self.parseHamplMerger, 'coombes' : self.parseCoombesMerger, 'watts' : self.parseWattsMerger, 'minimal' : self.parseMinimalMerger}
    self.DESTROYER_FACTORIES = {'membership' : self.parseMembershipDestroyer}
    self.GROUP_FACTORIES = {'simultaneous' : self.parseSimultaneousGroup, 'alternative' : self.parseAlternativeGroup, 'linear-tradeoff' : self.parseLinearTradeoff}
    self.ELEMENT_PARSERS = {'aggregator' : self.parseAggregator, 'changer' : self.parseChanger, 'merger' : self.parseMerger, 'verifier' : self.parseVerifier, 'destroyer' : self.parseDestroyer, 'fuzzier' : self.parseFuzzier, 'halter' : self.parseHalter, 'coloring' : self.parseColoring, 'overlap' : self.parseRegionOverlapping}
    self.no = 1 # stage index
    # parameter sequence from tool input
  
  def create(self, file):
    self.baseread(file)
    reg = Regionalizer(regionFactory=self.typeGet(self.dom.find('region'), self.REGION_FACTORIES))
    perfEl = self.dom.find('elements')
    for name in self.ELEMENT_PARSERS:
      reg.addElements(self.parseElements(perfEl.findall(name), self.ELEMENT_PARSERS[name]))
    stages = self.parseSequence(self.dom.find('algorithm'), 'stage', self.parseAlgorithmStage)
    stages.extend(self.parseSequence(self.dom.find('algorithm'), 'output', self.parseOutputStage))
    if not stages:
      stages = [self.parseStage(None, 0)] # must have at least one stage
    globals = self.parseStageItems(self.dom.find('algorithm').find('global'))
    for stage in stages:
      stage.addItems(globals)
    reg.addStages(stages)
    return reg
  
  # def informName(self, root):
    # metael = root.find('metadata')
    # if metael is None:
      # common.message('Algorithm metainformation not found')
    # else:
      # nameel = metael.find('name')
      # if nameel is None:
        # common.message('Algorithm metainformation incomplete: name not found')
      # else:
        # common.message('Running algorithm: {name}'.format(name=nameel.text))

  def parseElements(self, elements, method):
    return {self.strGet(subnode, 'id') : method(subnode) for subnode in elements}
  
  def parseSequence(self, node, subname, method):
    if node is None:
      return []
    items = []
    for subnode in node.findall(subname):
      items.append(method(subnode, no=self.no))
      self.no += 1
    return items
  
  def parseOutputParams(self, node):
    params = {}
    if node: # returns False also if it has no subelements, which is of no use as well
      colorEl = node.find('color')
      if colorEl:
        params['colorel'] = self.strGet(colorEl.find('fuzzier'), default=None)
        params['mixerName'] = self.strGet(colorEl.find('mixing'), default='additive')
      borderEl = node.find('border-effect')
      if borderEl:
        params['overlap'] = self.strGet(borderEl.find('merger'), default=None)
    return params

    
  def parseAggregator(self, node):
    return self.typeGet(node, self.AGGREGATOR_FACTORIES)(node, 
      target=self.typeGet(node, self.OBJECT_TARGETS, 'target'),
      sorterRef=self.strGet(node.find('external-ordering'), default=None),
      descending=self.boolGet(node.find('descending-ordering'), default=True),
      warnFail=self.boolGet(node.find('warn-fail'), default=True))
  
  def parseRingAggregator(self, node, **kwargs):
    return RingAggregator(
      targetCoreOnly=self.boolGet(node.find('target-core-only'), default=False),
      bidirectional=self.boolGet(node.find('bidirectional-flows'), default=True),
      tryMerge=self.boolGet(node.find('try-merge'), default=False),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      threshold=self.ratioGet(node.find('threshold')), **kwargs)
  
  def parseFlowAggregator(self, node, **kwargs):
    return FlowAggregator(
      targetCoreOnly=self.boolGet(node.find('target-core-only'), default=False),
      bidirectional=self.boolGet(node.find('bidirectional-flows'), default=True),
      tryChange=self.boolGet(node.find('try-change'), default=False),
      tryMerge=self.boolGet(node.find('try-merge'), default=False),
      useHinterlandFlows=self.boolGet(node.find('consider-hinterland-flows'), default=True),
      separateHinterland=self.boolGet(node.find('reassign-hinterland-separately'), default=False),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      transform=self.typeGet(node.find('transform'), self.AGGREGATION_TRANSFORMS, default='none'),
      indirectLinkage=self.typeGet(node.find('indirect-linkage'), self.AGGREGATION_SUBBINDS, default='none'),
      secondaryRef=self.strGet(node.find('secondary-criterion'), default=None), **kwargs)
  
  def parseNeighbourhoodAggregator(self, node, **kwargs):
    return NeighbourhoodAggregator(
      secondaryRef=self.strGet(node.find('secondary-criterion'), default=None), **kwargs)
  
  
  def parseChanger(self, node):
    return self.typeGet(node, self.CHANGER_FACTORIES)(node)
  
  def parseRelativeChanger(self, node):
    return RelativeChanger(protect=self.boolGet(node.find('protect')),
      threshold=self.ratioGet(node.find('threshold')),
      sorterRef=self.strGet(node.find('external-ordering'), default=None))

  
    
  def parseFuzzier(self, node):
    return self.typeGet(node, self.FUZZIER_FACTORIES, default=self.DEFAULT_FUZZIER_FACTORY)(node)
  
  def parseBasicFuzzier(self, node):
    fuz = BasicFuzzier(contiguity=self.ratioGet(node.find('exclave-penalization'), default=1))
    fuz.setActive(self.boolGet(node, 'active', default=True))
    return fuz
  
  def parseHamplFuzzier(self, node):
    fuz = HamplFuzzier(oscillation=self.ratioGet(node.find('oscillation'), default=1),
      contiguity=self.ratioGet(node.find('exclave-penalization'), default=1))
    fuz.setActive(self.boolGet(node, 'active', default=True))
    return fuz
  
  def parseSimberaFuzzier(self, node):
    fuz = SimberaFuzzier(contiguity=self.ratioGet(node.find('exclave-penalization'), default=1))
    fuz.setActive(self.boolGet(node, 'active', default=True))
    return fuz
  
  
  def parseHalter(self, node):
    return self.typeGet(node, self.HALTER_FACTORIES)(node)
  
  def parseCountHalter(self, node):
    return CountHalter(self.valueGet(node.find('threshold')))
  
  
  def parseMerger(self, node):
    return self.typeGet(node, self.MERGER_FACTORIES)(node)
  
  def parseHamplMerger(self, node):
    return HamplMerger(target=self.typeGet(node, self.PART_TARGETS, 'target'),
      threshold=self.ratioGet(node.find('threshold')),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      sorterRef=self.strGet(node.find('external-ordering'), default=None))
      
  def parseCoombesMerger(self, node):
    return CoombesMerger(target=self.typeGet(node, self.PART_TARGETS, 'target'),
      threshold=self.ratioGet(node.find('threshold')),
      toFlowRatio=self.ratioGet(node.find('to-flow')),
      counterFlowRatio=self.ratioGet(node.find('counter-flow')),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      sorterRef=self.strGet(node.find('external-ordering'), default=None))
  
  def parseWattsMerger(self, node):
    return WattsMerger(target=self.typeGet(node, self.PART_TARGETS, 'target'),
      threshold=self.ratioGet(node.find('threshold')),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      sorterRef=self.strGet(node.find('external-ordering'), default=None))

  def parseMinimalMerger(self, node):
    return MinimalMerger(target=self.typeGet(node, self.PART_TARGETS, 'target'),
      threshold=self.ratioGet(node.find('threshold')),
      neighcon=self.boolGet(node.find('neighbourhood'), default=False),
      sorterRef=self.strGet(node.find('external-ordering'), default=None))

  
  def parseDestroyer(self, node):
    return self.typeGet(node, self.DESTROYER_FACTORIES)(node)
  
  def parseMembershipDestroyer(self, node):
    return MembershipDestroyer(target=self.typeGet(node, self.OBJECT_TARGETS, 'target'),
      threshold=self.valueGet(node.find('threshold'), default=None),
      exclave=self.boolGet(node.find('exclave'), default=False))
      
  
  def parseVerifier(self, node):
    grouproot = node.find('group')
    critroot = node.find('criterion')
    if grouproot is None:
      if critroot is None:
        raise ConfigError, 'verifier with no criteria specified'
      else:
        verif = self.parseCriterion(critroot)
    else:
      verif = self.parseGroup(grouproot)
    verif.setActive(self.boolGet(node, 'active', default=True))
    return verif
    
  def parseCriterion(self, node):
    critClass = self.typeGet(node, self.CRITERIA)
    value = self.ratioGet(node) if critClass.ratio else self.valueGet(node)
    return critClass(min=self.typeGet(node, self.THRESHOLD_DIRECTIONS, 'direction'), value=value)

  def parseGroup(self, node):
    groupFactory = self.typeGet(node, self.GROUP_FACTORIES)
    siblings = []
    for grnode in node.findall('group'):
      siblings.append(self.parseGroup(grnode))
    for simpnode in node.findall('criterion'):
      siblings.append(self.parseCriterion(simpnode))
    # TODO: parse additional group parameters (tradeoff etc)
    return groupFactory(siblings)
  
  def parseSimultaneousGroup(self, siblings):
    return SimultaneousGroup(siblings)
  
  def parseAlternativeGroup(self, siblings):
    return AlternativeGroup(siblings)
  
  def parseLinearTradeoff(self, siblings):
    if len(siblings) != 2:
      raise ConfigError, 'linear tradeoff verifier requires exactly 2 criteria, {} found'.format(len(siblings))
    return LinearTradeoffGroup(siblings)
  
  def parseColoring(self, node):
    try:
      value = self.strGet(node.find('mixer'), default='additive').lower()
      return ZoneColoring(mixer=colors.COLOR_MIXERS[value])
    except KeyError:
      raise ConfigError, 'unknown color mixing function ({}), allowed: {}'.format(value, ', '.join(colors.COLOR_MIXERS.keys()))
  
  def parseRegionOverlapping(self, node):
    return RegionOverlapping()
  
  def parseAlgorithmStage(self, node, no):
    stage = AlgorithmStage(message=self.strGet(node, 'message', default='running'), no=no)
    stage.addItems(self.parseStageItems(node))
    return stage
  
  def parseOutputStage(self, node, no):
    stage = OutputStage(message=self.strGet(node, 'message', default='running'), no=no)
    stage.addItems(self.parseStageItems(node))
    return stage
  
  def parseStageItems(self, node):
    if node:
      return [ElementReference(subnode.tag, self.strGet(subnode, 'id')) for subnode in node]
    else:
      return []
  

def getMainParamCount(): return 26
def getFileParamCount(): return 14

def run(regionalizer, loader, delimit=True):
  loader.load()
  if delimit:
    regionalizer.run(loader.getZoneList())
  loader.output(regionalizer)
  
def runByParams(zoneLayer, zoneIDFld, zoneMassFld, zoneCoopFld='', zoneRegFld='', zoneColFld='', coreQuery='', outRegFld='R', doOutCoreStr='true', doOutColorStr='false', outOverlapTable='', measureFldsStr='', interTable='', interFromIDFld='', interToIDFld='', interStrFld='', interLenFld='', neighTable='', algorithmFile='', *args, **kwargs):
  delimit = kwargs['delimit'] if 'delimit' in kwargs else False
  common.progress('loading delimiter setup')
  reg = DRSetupReader(parameters=[(None if not param else param) for param in args]).create(algorithmFile)
  common.progress('initializing data load')
  loader = loaders.RegionalLoader(reg)
  loader.sourceOfZones(zoneLayer, {'id' : zoneIDFld, 'mass' : zoneMassFld, 'color' : zoneColFld}, targetClass=objects.MonoZone)
  loader.sourceOfPresets({'assign' : zoneRegFld, 'coop' : zoneCoopFld})
  loader.sourceOfInteractions(interTable, {'from' : interFromIDFld, 'to' : interToIDFld, 'value' : interStrFld})
  loader.possibleNeighbourhood(neighTable)
  setOutputs(loader, outRegFld, doOutCoreStr, doOutColorStr, measureFldsStr, outOverlapTable, delimit)
  run(reg, loader, delimit=delimit)

def runByFile(inputsFile, algorithmFile, outRegFld='R', doOutCoreStr='true', doOutColorStr='false', measureFldsStr='', outOverlapTable='', *args, **kwargs):
  delimit = kwargs['delimit'] if 'delimit' in kwargs else False
  common.progress('loading delimiter setup')
  reg = DRSetupReader(parameters=[(None if not param else param) for param in args]).create(algorithmFile)
  loader = loaders.RLSetupReader().create(inputsFile)
  setOutputs(loader, outRegFld, doOutCoreStr, doOutColorStr, measureFldsStr, outOverlapTable, delimit)
  run(reg, loader, delimit=delimit)
  
def setOutputs(loader, regFld, doOutCoreStr, doOutColorStr, measureFldsStr, outOverlapTable, delimit=True):
  loader.addZoneOutputSlot('assign', regFld, require=delimit)
  if common.toBool(doOutCoreStr, 'core field output switch'):
    loader.addZoneOutputSlot('core', regFld + '_CORE')
  if common.toBool(doOutColorStr, 'color field output switch'):
    loader.addZoneOutputSlot('color', regFld + '_COL')
  for measure in common.parseFields(measureFldsStr):
    loader.addZoneOutputSlot(measure, measure)
  if outOverlapTable:
    loader.setOverlapOutput(outOverlapTable)

if __name__ == '__main__':
  import sys
  DRSetupReader().createRegionalizer(sys.argv[1])