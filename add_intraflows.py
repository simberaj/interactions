import common, loaders# , regionalization

# OUT_MEASURES = {'TOT_IN_CORE' : 'IN', 'TOT_OUT_CORE' : 'OUT'}
ZONE_MASS_TYPE = {'JOBS' : False, 'EA' : True}

with common.runtool(8) as parameters:
  zoneLayer, zoneIDFld, zoneMassFld, massType, interLayer, interFromIDFld, interToIDFld, interStrengthFld = parameters
  try:
    subtractOutflows = ZONE_MASS_TYPE[massType]
  except KeyError:
    raise ValueError, 'invalid mass type: {}, JOBS or EA allowed'.format(massType)
  zoneSlots = {'id' : zoneIDFld, 'mass' : zoneMassFld}
  interSlots = {'from' : interFromIDFld, 'to' : interToIDFld, 'value' : interStrengthFld}
  # measuresToSlots = {}
  # outSlots = {}
  # for measure in OUT_MEASURES:
    # measuresToSlots[measure] = []
    # for fld in interFlds:
      # slotName = fld + '_' + OUT_MEASURES[measure]
      # measuresToSlots[measure].append(slotName)
      # outSlots[slotName] = slotName
  regload = loaders.RegionalLoader()
  # regionalization.Regionalizer(objects.FunctionalRegion))
  regload.sourceOfZones(zoneLayer, zoneSlots)
  regload.sourceOfInteractions(interLayer, interSlots)
  regload.load()
  zonelist = regload.getZoneList()
  prog = common.progressor('calculating intraflows', len(zonelist))
  intraDict = {}
  for zone in zonelist:
    intraflow = zone.getMass() - zone.sumFlows(out=subtractOutflows)
    if intraflow > 0:
      id = zone.getID()
      intraDict[id] = {id : intraflow}
    prog.move()
  prog.end()
  # common.progress('writing ')  
  loaders.InteractionWriter(interLayer, interSlots, append=True).write(intraDict, text='writing intraflows')

