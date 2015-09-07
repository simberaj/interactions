import arcpy, common, loaders

def createSelectQuery(where, fld, vals, quote=False):
  return common.query(where, '[%s] IN (', fld) + ', '.join(
    ("'" + unicode(val) + "'" if quote else unicode(val)) for val in vals
  ) + ')'

def eligibleEnds(rels, endIDs, invert=False):
  sources = set()
  targets = set()
  for source in rels:
    if (source in endIDs) ^ invert:
      sources.add(source)
      for target in rels[source]:
        if (target in endIDs) ^ invert:
          targets.add(target)
  return sources, targets

with common.runtool(8) as parameters:
  table, fromIDField, toIDField, places, placesIDField, placeQuery, invertStr, output = parameters
  invert = common.toBool(invertStr, 'place search inversion')
  common.progress('loading places')
  placeIDs = set(loaders.OneFieldReader(places, placesIDField, where=placeQuery).read())
  if placeIDs:
    # hack to retrieve random element from set
    for id in placeIDs: break
    quote = isinstance(id, str) or isinstance(id, unicode)
    common.progress('loading interactions')
    interRels = loaders.NeighbourTableReader(table, {'from' : fromIDField, 'to' : toIDField}).read()
    common.progress('preparing selection query')
    sources, targets = eligibleEnds(interRels, placeIDs, invert)
    qry = '(' + createSelectQuery(table, fromIDField, sources, quote=quote) + ') AND (' + createSelectQuery(table, toIDField, targets, quote=quote) + ')'
    common.progress('selecting interactions')
    print table, output, qry
    common.select(table, common.addTableExt(output), qry)
  else:
    common.warning('No places found')