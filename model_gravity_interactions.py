import arcpy, common, modeling, loaders

REPORT_TEMPLATE = u'''Interaction gravity modelling analysis

Input interactions: %s
Interaction selection query: %s
Origin mass field (m1): %s
Destination mass field (m2): %s
Interaction real strength field: %s
Interaction length field (d): %s
Output model strength field: %s

Optimization method used: %s
Interactions found: %i
Using gravity model in form G*m1*m2*d^(-B)

MODEL OUTPUT
Calculated parameters calibrated on real interactions
B parameter value: %g
G parameter value: %g

STATISTICAL ANALYSIS

'''

with common.runtool(9) as parameters:
  interactions, selQuery, massFromFld, massToFld, interactFld, lengthFld, optimizationMethod, outputFld, reportFileName = parameters
    
  ## ASSEMBLE INPUT
  common.progress('counting interactions')
  count = common.count(interactions)
  if count == 0:
    raise ValueError, 'no interactions found'
  common.message('Found ' + str(count) + ' interactions.')

  common.progress('loading interactions')
  modelInters = loaders.BasicReader(interactions, {'strength' : interactFld, 'distance' : lengthFld, 'massFrom' : massFromFld, 'massTo' : massToFld}, targetClass=modeling.GravityInteraction, where=selQuery).read()
  # rows = arcpy.SearchCursor(interactions, selQuery)
  # modelInters = []
  # for row in rows:
    # try:
      # modelInters.append(GravityInteraction(row.getValue(interactFld), row.getValue(lengthFld), row.getValue(massFromFld), row.getValue(massToFld)))
    # except ValueError:
      # pass # neplatna interakce
  
  ## OPTIMALIZE
  common.progress('creating gravity model')
  opt = modeling.GravityOptimizer(modelInters)
  common.progress('optimizing model parameters')
  opt.optimize(optimizationMethod)
  common.message('Model parameters found:')
  common.message('B parameter value: ' + str(opt.getB()))
  common.message('G parameter value: ' + str(opt.getG()))
  common.progress('calculating model interactions')
  modelStrengths = opt.theoreticalInteractions()
  common.progress('calculating residuals')
  report = opt.report(modelStrengths)
  common.message('\nStatistical report\n\n' + report)
  common.progress('saving model interactions')
  loaders.SequentialUpdater(interactions, {'s' : outputFld}, where=selQuery).update([{'s' : st} for st in modelStrengths])
  # rows = arcpy.UpdateCursor(interactions, selQuery)
  # i = 0
  # for row in rows:
    # row.setValue(outputFld, modelStrengths[i])
    # rows.updateRow(row)
    # i += 1
    
  if reportFileName:
    common.progress('creating report')
    out = (REPORT_TEMPLATE % (interactions, selQuery, massFromFld, massToFld, interactFld, lengthFld, outputFld, optimizationMethod, count, opt.getB(), opt.getG())) + report
    opt.writeReport(out, reportFileName)
