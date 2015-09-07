import common
from conversion import SpatialMatrixNeighbourLinker

with common.runtool(5) as parameters:
  zoneAreas, zoneIDFld, method, location, outputName = parameters
  linker = SpatialMatrixNeighbourLinker(zoneAreas, zoneIDFld, method, location)
  linker.process()
  linker.output(outputName)
  linker.close()
