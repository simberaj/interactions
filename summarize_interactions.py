import common, objects, loaders, regionalization

OUT_MEASURES = {'TOT_IN_CORE' : 'IN', 'TOT_OUT_CORE' : 'OUT'}

with common.runtool(7) as parameters:
  zoneLayer, zoneIDFld, zoneTargetQuery, interLayer, interStrengthFlds, \
    interFromIDFld, interToIDFld = parameters
  interFlds = common.parseFields(interStrengthFlds)
  zoneInSlots = {'id' : zoneIDFld}
  objects.MultiInteractions.setDefaultLength(len(interFlds))
  objects.MonoZone.interactionClass = objects.MultiInteractions
  interSlots = {'from' : interFromIDFld, 'to' : interToIDFld}
  interSlots.update({fld : fld for fld in interFlds})
  measuresToSlots = {}
  outSlots = {}
  for measure in OUT_MEASURES:
    measuresToSlots[measure] = []
    for fld in interFlds:
      slotName = fld + '_' + OUT_MEASURES[measure]
      measuresToSlots[measure].append(slotName)
      outSlots[slotName] = slotName
  regload = loaders.RegionalLoader(regionalization.Regionalizer(objects.FunctionalRegion))
  regload.sourceOfZones(zoneLayer, zoneInSlots, targetClass=objects.MonoZone, coreQuery=zoneTargetQuery)
  regload.sourceOfMultiInteractions(interLayer, interSlots)
  regload.load()
  common.progress('summarizing')
  measurer = objects.ZoneMeasurer()
  zoneData = {}
  for zone in regload.getZoneList():
    zoneID = zone.getID()
    zoneData[zoneID] = {}
    for measure in OUT_MEASURES:
      vec = measurer.getMeasure(zone, measure)
      print zone, measure, vec
      for i in range(len(interFlds)):
        zoneData[zoneID][measuresToSlots[measure][i]] = float(vec[i])
  loaders.ObjectMarker(zoneLayer, zoneInSlots, outSlots).mark(zoneData)

  # zoneLoader.outputMultiMeasures(zones, interactionLoader.getStrengthFieldNames(), measures=['TOT_IN_CORE', 'TOT_OUT_CORE'], aliases=['INSUM', 'OUTSUM'])
