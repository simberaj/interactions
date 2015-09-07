## IMPORT MODULES
import sys
sys.path.append('.')
import common # useful shortcut functions for arcpy and datamodel
import delimit_functional_regions

common.debugMode = True
common.progress('loading tool parameters')
# whoa, have fun with the parameters
zoneLayer, \
zoneIDFld, zoneMassFld, zoneCoopFld, zoneRegFld, zoneColFld, coreQuery, \
outRegFld, doOutCoreStr, outColFld, measureFlds, \
interTable, interFromIDFld, interToIDFld, interStrFld, \
neighTable, exclaveReassignStr, oscillationStr, doSubBindStr, doCoreFirstStr, \
aggregSorterStr, threshold1Str, threshold2Str = common.parameters(23)

delimit_functional_regions.main(zoneLayer, zoneIDFld, zoneMassFld, zoneCoopFld, zoneRegFld, zoneColFld, coreQuery, outRegFld, doOutCoreStr, outColFld, measureFlds, interTable, interFromIDFld, interToIDFld, interStrFld, neighTable, exclavePenalStr=('100' if common.toBool(exclaveReassignStr, 'exclave reassignment switch') else '0'), aggregSorterStr=aggregSorterStr, verifier1Str='MASS', threshold1Str=threshold1Str, verifier2Str='HINTERLAND_MASS', threshold2Str=threshold2Str, oscillationStr=oscillationStr, doSubBindStr=doSubBindStr, doCoreFirstStr=doCoreFirstStr)

