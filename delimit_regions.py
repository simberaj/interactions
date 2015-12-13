import common, regionalization

with common.runtool(regionalization.getMainParamCount()) as parameters:
  import cProfile
  # cProfile.run('regionalization.runByParams(*parameters, delimit=True)')
  regionalization.runByParams(*parameters, delimit=True)
