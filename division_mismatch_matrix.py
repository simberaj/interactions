import common, objects, loaders, regionalization, collections

with common.runtool(6) as parameters:
  zoneLayer, idFld, massFld, reg1Fld, reg2Fld, outPath = parameters
  common.progress('loading zones')
  zones = []
  for regFld in (reg1Fld, reg2Fld):
    loader = loaders.RegionalLoader(regionalization.Regionalizer(objects.PlainRegion))
    loader.sourceOfZones(zoneLayer, {'id' : idFld, 'mass' : massFld}, targetClass=objects.NoFlowZone)
    loader.sourceOfPresets({'assign' : regFld})
    loader.load()
    zones.append(loader.getZoneDict())
  common.progress('computing mismatch')
  mismatch = collections.defaultdict(lambda: collections.defaultdict(float))
  for id in zones[0]:
    reg1 = zones[0][id].getRegion()
    if reg1 is not None: reg1 = reg1.getID()
    reg2 = zones[1][id].getRegion()
    if reg2 is not None: reg2 = reg2.getID()
    mass = zones[0][id].getMass()
    mismatch[reg1][reg2] += mass
  common.progress('saving')
  loaders.InteractionWriter(outPath, {'from' : 'REG_1', 'to' : 'REG_2', 'value' : 'MASS'}).saveRelations(mismatch)