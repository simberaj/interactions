import arcpy, common, loaders

ASSIGNED = 'tmp_z057'

with common.runtool(11) as parameters:
  zones, idFld, regionFld, coopFld, regTransFldsStr, nameFldsStr, sumCoreFldsStr, countCoresStr, sumAllFldsStr, countAllStr, outPath = parameters
  # parse field lists
  nameFlds = common.parseFields(nameFldsStr)
  regTransFlds = common.parseFields(regTransFldsStr)
  if regionFld in regTransFlds: regTransFlds.remove(regionFld)
  sumCoreFlds = common.parseFields(sumCoreFldsStr)
  sumAllFlds = common.parseFields(sumAllFldsStr)
  coreTrans = {fld : 'CORE_' + fld for fld in sumCoreFlds}
  allTrans = {fld : 'ALL_' + fld for fld in sumAllFlds}
  outSumFlds = coreTrans.values() + allTrans.values()
  coreTransItems = coreTrans.items()
  allTransItems = allTrans.items()
  countCores = common.toBool(countCoresStr, 'core count switch')
  countAll = common.toBool(countAllStr, 'zone count switch')

  zoneSlots = {'id' : idFld, 'assign' : regionFld}
  if coopFld:
    zoneSlots['core'] = coopFld
  for fld in set(nameFlds + regTransFlds + sumCoreFlds + sumAllFlds):
    zoneSlots[fld] = fld
    
  common.progress('reading zone data')
  zoneData = loaders.DictReader(zones, zoneSlots).read()
  print zoneData
  
  common.progress('computing region statistics')
  regionData = {} # TODO: pattern dict to be copied, will fasten
  for zoneDict in zoneData.itervalues():
    id = zoneDict['id']
    regID = zoneDict['assign']
    if regID is None: # no assignment -> will fall out of the result
      continue
    if regID not in regionData: # new region detected, create initial values
      regionData[regID] = {'id' : regID, 'coreids' : []}
      for outFld in outSumFlds:
        regionData[regID][outFld] = 0
      for fld in regTransFlds:
        regionData[regID][fld] = None
      if countCores:
        regionData[regID]['CORE_COUNT'] = 0
      if countAll:
        regionData[regID]['ALL_COUNT'] = 0
    myreg = regionData[regID]
    if id == regID: # main core zone detected
      for mainFld in regTransFlds: # direct transfer field
        myreg[mainFld] = zoneDict[mainFld]
    if id == regID or (coopFld and zoneDict['core'] == regID): # core zone detected
      myreg['coreids'].append(id)
      for coreFld, outCoreFld in coreTransItems:
        myreg[outCoreFld] += zoneDict[coreFld]
      if countCores:
        myreg['CORE_COUNT'] += 1
    for allFld, outAllFld in allTransItems: # and anyway
      myreg[outAllFld] += zoneDict[allFld]
    if countAll:
      myreg['ALL_COUNT'] += 1
  print regionData
  
  # assemble the names
  common.progress('assembling region names')
  for regDict in regionData.itervalues():
    coreIDs = regDict['coreids']
    if len(coreIDs) == 1:
      for nameFld in nameFlds:
        name = zoneData[coreIDs[0]][nameFld]
        # common.debug(name, type(name))
        if isinstance(name, unicode):
          regDict[nameFld] = name
        elif isinstance(name, str):
          regDict[nameFld] = unicode(name, 'utf8')
        else:
          regDict[nameFld] = unicode(str(name), 'utf8')
    else: # sort so that the main core is first (provisional)
      if regDict['id'] in coreIDs:
        coreIDs.remove(regDict['id'])
        coreIDs.insert(0, regDict['id'])
      for nameFld in nameFlds:
        regDict[nameFld] = []
        for regid in coreIDs:
          regDict[nameFld].append(zoneData[regid][nameFld])
        regDict[nameFld] = u'-'.join(unicode(name if isinstance(name, str) else str(name), 'utf8') for name in regDict[nameFld])
    del regDict['coreids']
  print regionData
    
  ## DISSOLVE
  # whole region statstics
  # allStats = createStats(sumAllFlds, idFld, [], common.toBool(countAll, 'zone count switch'))
  common.progress('selecting regions')
  common.selection(zones, ASSIGNED, '{} IS NOT NULL'.format(regionFld)) # exclude unassigned
  common.progress('dissolving')
  arcpy.Dissolve_management(ASSIGNED, outPath, [regionFld])
  
  # and update
  # create slots
  outSlots = {fld : fld for fld in regTransFlds + nameFlds + outSumFlds}
  if countCores: outSlots['CORE_COUNT'] = 'CORE_COUNT'
  if countAll: outSlots['ALL_COUNT'] = 'ALL_COUNT'
  # outSlots.update(coreTrans)
  # outSlots.update(allTrans)
  # common.debug(outSlots, coreTrans, allTrans, regTransFlds, nameFlds)
  
  loaders.ObjectMarker(outPath, {'id' : regionFld}, outSlots, outTypes=loaders.inferFieldTypes(regionData.values(), outSlots)).mark(regionData, 'writing names and statistics')
    
   
  # cores = bool(coopFld)
  # # ASSEMBLE REGION NAMES
  # if coopFld:
    # common.progress('retrieving core information')
    # inDict = {'id' : idFld, 'region' : regionFld, 'coop' : coopFld}
    # inDict.update({fld : fld for fld in nameFlds})
    # reader = loaders.DictReader(zones, inDict)
    # coredata = reader.read()
  
  # common.progress('retrieving core information')
   
  # cores = {} # region for each core zone
  # names = collections.defaultdict(dict) # list of region names
  # rows = arcpy.SearchCursor(zones)
  # for row in rows:
    # merge = None
    # if coopFld:
      # coopID = row.getValue(coopFld)
      # if coopID: # if it is a lesser (cooperating) core
        # merge = coopID
        # id = row.getValue(idFld)
    # if not merge: # if it is not a lesser core
      # id = row.getValue(idFld)
      # regID = row.getValue(regionFld)
      # if id == regID: # if it is a main core
        # merge = regID
    # if merge: # a core zone
      # cores[id] = merge
      # for nameFld in nameFlds: # assemble names
        # nameVal = row.getValue(nameFld)
        # if nameFld in names[merge]:
          # names[merge][nameFld] += (u'-' + unicode(nameVal))
        # else:
          # names[merge][nameFld] = unicode(nameVal)
  # idFldType = common.fieldType(type(id))
  # del rows
  
  # MAKE CORE INFORMATION
  # fldList = None
  # if cores:
    # common.progress('assembling core fields')
    # fldList = common.fieldList(zones)
    # coreDict = {'core' : TMP_CORE_FLD}
    # coreDict.update({nameFld : 'C_' + nameFld for nameFld in nameFlds})
    # outNameFlds = coreDict.values()
    # outNameFlds.remove(TMP_CORE_FLD)
    # if TMP_CORE_FLD not in fldList:
      # arcpy.AddField_management(zones, TMP_CORE_FLD, idFldType)  # core-of-region field
    # name fields
    # for outNameFld in outNameFlds:
      # if outNameFld not in fldList:
        # arcpy.AddField_management(zones, outNameFld, 'TEXT')
    # write core-of region and name fields
    # common.progress('writing core information')
    # updater = loaders.ObjectMarker(zones, {'id' : idFld}, coreDict)
    # updater.mark(names)
    # rows = arcpy.UpdateCursor(zones)
    # for row in rows:
      # id = row.getValue(idFld)
      # if id in cores:
        # row.setValue(TMP_CORE_FLD, cores[id])
        # for i in range(len(nameFlds)):
          # row.setValue(outNameFlds[i], names[cores[id]][nameFlds[i]])
      # rows.updateRow(row)
    # del rows
  
    # # CREATE CORE SUMMARIES
    # common.progress('calculating core statistics')
    # coreStats = createStats(sumCoreFlds, TMP_CORE_FLD, outNameFlds,
      # common.toBool(countCores, 'core count switch'))
    # if coreStats:
      # arcpy.Statistics_analysis(zones, TMP_CORE_TABLE, coreStats, TMP_CORE_FLD)
  

  # common.progress('joining region information')
  # if regTransFlds:
    # arcpy.JoinField_management(outName, regionFld, zones, regionFld, regTransFlds)
  
  # if cores:
    # common.progress('joining core information')
    # arcpy.JoinField_management(outName, regionFld, TMP_CORE_TABLE, TMP_CORE_FLD, common.statListToFields(coreStats))
    # common.progress('deleting temporary fields')
    # arcpy.DeleteField_management(zones, outNameFlds + [TMP_CORE_FLD])
# TMP_CORE_FLD = 'CORE'
# TMP_CORE_TABLE = 'tmp_cores'

# def createStats(sumFlds, idFld, transferFlds, count=True):
  # stats = []
  # for sumFld in sumFlds:
    # stats.append([sumFld, 'SUM'])
  # if count:
    # stats.append([idFld, 'COUNT'])
  # for fld in transferFlds:
    # stats.append([fld, 'FIRST'])
  # return stats
    

