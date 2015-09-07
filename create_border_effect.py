import arcpy, os, common, collections, loaders

OVERLAP_FLD = 'OVERLAP'
TMP_BORDS = 'tmp_borders'
PTOL_LEFT_FLD = 'LEFT_FID'
PTOL_RIGHT_FLD = 'RIGHT_FID'

with common.runtool(7) as parameters:
  regions, idFld, overlapTable, idFrom, idTo, overlapFld, outBorders = parameters
  common.progress('creating borders')
  tmpBords = common.featurePath(os.path.dirname(outBorders), TMP_BORDS)
  arcpy.PolygonToLine_management(regions, tmpBords, 'IDENTIFY_NEIGHBORS')
  # dissolve to remove line duplication on shared borders
  common.progress('removing border duplicates')
  arcpy.Dissolve_management(tmpBords, outBorders, [PTOL_LEFT_FLD, PTOL_RIGHT_FLD])
  common.progress('loading region identifiers')
  oidFld = arcpy.Describe(regions).OIDFieldName
  idReader = loaders.DictReader(regions, {'id' : idFld, 'fid' : oidFld})
  regions = idReader.read()
  regIDType = type(next(regions.itervalues()))
  common.progress('loading region overlap values')
  overlapReader = loaders.OverlapReader(overlapTable, {'from' : idFrom, 'to' : idTo, 'value' : overlapFld})
  overlaps = overlapReader.read()
  # remap to FIDs
  tofid = {}
  for id, valdict in overlaps.iteritems():
    fid = regions[id]['fid']
    tofid[fid] = {}
    for toid, toval in valdict.iteritems():
      tofid[fid][regions[toid]['fid']] = {'from' : id, 'to' : toid, 'value' : toval}
  common.progress('writing border effects')
  marker = loaders.OverlapMarker(outBorders,
    inSlots={'from' : PTOL_LEFT_FLD, 'to' : PTOL_RIGHT_FLD},
    outSlots={'from' : common.NEIGH_FROM_FLD, 'to' : common.NEIGH_TO_FLD, 'value' : OVERLAP_FLD},
    where=('{} <> -1 AND {} <> -1'.format(PTOL_LEFT_FLD, PTOL_RIGHT_FLD)))
  marker.mark(tofid)
  common.progress('removing temporary files')
  common.delete(tmpBords)
