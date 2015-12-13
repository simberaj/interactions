import common, objects, loaders, regionalization, collections, operator

INTRAFLOW_MODES = {'NONE' : [], 'ALL' : [(True, True, True, True)], 'CORE-HINTERLAND' : [(True, False, False, True), (False, True, True, False)], 'CORE-CORE' : [(True, False, True, False)], 'CORE-(CORE+HINTERLAND)' : [(True, False, True, True), (False, True, True, False)]}

with common.runtool(11) as parameters:
  common.progress('loading settings')
  zoneLayer, zoneIDFld, zoneRegFld, zoneCoreFld, aggregMode, intraflowMode, \
    interLayer, interFromIDFld, interToIDFld, aggregFldsStr, outPath = parameters
  # set up data loading
  regload = loaders.RegionalLoader(regionalization.Regionalizer(objects.FunctionalRegion))
  regload.sourceOfZones(zoneLayer, {'id' : zoneIDFld}, targetClass=objects.MonoZone)
  regload.sourceOfPresets({'assign' : zoneRegFld, 'coop' : zoneCoreFld})
  interDict = {'from' : interFromIDFld, 'to' : interToIDFld}
  aggregFlds = common.parseFields(aggregFldsStr)
  interDict.update({fld : fld for fld in aggregFlds})
  regload.sourceOfMultiInteractions(interLayer, interDict, ordering=aggregFlds)
  # flow aggregation mode
  regSrc, regTgt = aggregMode.split('-')
  hinterSrc = bool(regSrc != 'CORE')
  coreTgt = bool(regTgt == 'CORE')
  try:
    intraFlowSetting = INTRAFLOW_MODES[intraflowMode]
  except KeyError:
    raise ValueError, 'unknown intraflow setting: ' + intraflowMode
  # load the data
  regload.load()
  # aggregate
  regs = regload.getRegionalizer().getRegions()
  common.progress('aggregating flows')
  flows = {}
  for region in regs:
    rawFlows = region.getOutflows(hinter=hinterSrc)
    flows[region] = (rawFlows.toCore() if coreTgt else rawFlows.toRegional()).restrictToRegions()
    for setting in intraFlowSetting:
      flows[region][region] += region.getIntraflows(*setting).sum()
  # raise RuntimeError
  common.progress('writing output')
  loaders.MultiInteractionWriter(outPath, interDict, convertToID=True).write(flows)
