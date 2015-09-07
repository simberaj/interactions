import arcpy, sys, os
sys.path.append('.')
import common
from networking import BulkConnectionCreator
arcpy.env.overwriteOutput = 1

# Creates a neighbourhood table of provided zones according to the principle of network neighbourhood - two zones are neighbours if they are connected by a route along the network that does not pass through a third settlement and that is most reasonable according to the provided impedance
# Settlement areas must not cross zone boundaries!

TMP_ZONE_NEGBUF = 'tmp_zonecore'
TMP_SETTL_NEGBUF = 'tmp_settlcore'
TMP_ROUTES = 'tmp_routes'
TMP_ROUTE_ER = 'tmp_rerase'
TMP_ROUTE_SINGLE = 'tmp_rsing'
TMP_RSING_LAY = 'tmp_rsing_lay'

common.progress('parsing attributes')
zoneAreas, zonePts, zoneIDFld, settlAreas, network, impedance, cutoff, cutoffFld, numToFind, location, outputName = common.parameters(11)
common.progress('initializing route creator')
# create network connections - see comments for create_network_connections
conn = BulkConnectionCreator(zonePts, network, impedance, cutoff, numToFind, location)
common.progress('loading data')
conn.load()
common.progress('solving routes')
conn.solve()
common.progress('joining attributes')
conn.joinFields([zoneIDFld])
common.progress('creating routes')
conn.output(TMP_ROUTES) # routes between the zone central points
conn.close()
arcpy.env.workspace = location
# prepare the settlement areas - remove all lying close to the border
common.progress('clipping settlement areas')
arcpy.Buffer_analysis(zoneAreas, TMP_ZONE_NEGBUF, '-' + borderDist)
arcpy.Clip_analysis(settlAreas, TMP_ZONE_NEGBUF, TMP_SETTL_NEGBUF)
# cut the routes by settlement areas -> connections between them (most expensive)
common.progress('creating settlement connections')
arcpy.Erase_analysis(TMP_ROUTES, TMP_SETTL_NEGBUF, TMP_ROUTE_ER)
# explode multipart routes (pass through a settlement)
common.progress('exploding multipart routes')
arcpy.MultipartToSinglepart_management(TMP_ROUTE_ER, TMP_ROUTE_SINGLE)
# disregard all route parts contained entirely within a single zone
common.progress('selecting routes between zones')
arcpy.MakeFeatureLayer_management(TMP_ROUTE_SINGLE, TMP_RSING_LAY)
arcpy.SelectLayerByLocation_management(TMP_RSING_LAY, 'COMPLETELY_WITHIN', zoneAreas)
arcpy.SelectLayerByAttribute_management(TMP_RSING_LAY, 'SWITCH_SELECTION')
# non-duplicate entries for the zone IDs are the searched connections
# create an output table (fields will be added later)
common.progress('creating output table')
outputPath = arcpy.CreateTable_management(location, outputName).getOutput(0)
oIDFld = 'O_%s' % zoneIDFld
dIDFld = 'D_%s' % zoneIDFld
# order the rows so that identical tuples of O_ID, D_ID are next to each other
sorter = '%s; %s' % (dIDFld, oIDFld) # should be the same as input ordering
common.progress('starting route search')
connRows = arcpy.SearchCursor(TMP_RSING_LAY, '', '', '', sorter)
prevOID = None
prevDID = None
prevImp = None
start = True
sequence = False # if a sequence of identical tuples of O_ID, D_ID has been detected
for connRow in connRows:
  oID = connRow.getValue(oIDFld)
  dID = connRow.getValue(dIDFld)
  impedVal = connRow.getValue(impedance)
  if start: # start at the second row
    start = False
    # add fields to output table and open cursor
    common.progress('preparing output table')
    arcpy.AddField_management(outputPath, common.NEIGH_FROM_FLD, common.fieldType(type(oID)))
    arcpy.AddField_management(outputPath, common.NEIGH_TO_FLD, common.fieldType(type(dID)))
    arcpy.AddField_management(outputPath, impedance, common.fieldType(type(impedVal)))
    common.progress('opening output table')
    outputRows = arcpy.InsertCursor(outputPath)
    common.progress('writing output')
  else:
    if oID == prevOID and dID == prevDID: # same as previous, detect sequence
      sequence = True
    else:
      if sequence: # end of sequence, disregard it
        sequence = False
      else: # unique record - add neighbour record
        outRow = outputRows.newRow()
        outRow.setValue(common.NEIGH_FROM_FLD, prevOID)
        outRow.setValue(common.NEIGH_TO_FLD, prevDID)
        outRow.setValue(impedance, prevImp)
        outputRows.insertRow(outRow)
  prevOID = oID
  prevDID = dID
  prevImp = impedVal

del connRows, outputRows

common.progress('deleting temporary files')
# try: # delete temporary files
  # arcpy.Delete_management(TMP_ZONE_NEGBUF)
  # arcpy.Delete_management(TMP_SETTL_NEGBUF)
  # arcpy.Delete_management(TMP_ROUTES)
  # arcpy.Delete_management(TMP_ROUTE_ER)
  # arcpy.Delete_management(TMP_ROUTE_SINGLE)
# except:
  # pass

common.done()
