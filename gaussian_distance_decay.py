import arcpy, common, loaders
from modeling import GaussianOptimizer

REPORT_TEMPLATE = u'''Interaction Gaussian modelling analysis

Input interactions: %s
Interaction strength field: %s
Interaction length field (d): %s
Output decayed strength field: %s

Interactions found: %i
Using Gaussian model in form G * e^(-d^2 / (qB))
Decay rapidity correction coefficient q: %g

MODEL OUTPUT
Calculated parameters calibrated on real interaction length quantile strength sums
(empirical variogram fitting)
B parameter value: %g
G parameter value: %g
Quantiles (bins) used: %s

STATISTICAL ANALYSIS

'''

with common.runtool(7) as parameters:
  interactions, strengthFld, lengthFld, quantileN, coefStr, outputFld, reportFileName = parameters
  coef = common.toFloat(coefStr, 'distance-decay coefficient')
   
  ## ASSEMBLE INPUT
  common.progress('counting interactions')
  count = common.count(interactions)
  if count == 0:
    raise ValueError, 'no interactions found'
  common.message('Found ' + str(count) + ' rows.')

  common.progress('loading interactions')
  modelInters = loaders.BasicReader(interactions, {'strength' : strengthFld, 'length' : lengthFld}).read()
  
  # if i > 0:
    # common.warning('%i interactions failed to load due to invalid value' % i)
    
  ## OPTIMALIZE
  common.progress('creating distance-decay model')
  opt = GaussianOptimizer.fromData(modelInters, qnum=int(quantileN))
  common.progress('optimizing model parameters')
  opt.optimize()
  common.message('Model parameters found:')
  common.message('B parameter value: ' + str(opt.getB()))
  common.message('G parameter value: ' + str(opt.getG()))
  # common.progress('creating decayed interaction field')
  # arcpy.AddField_management(interactions, outputFld, 'DOUBLE')
  common.progress('saving decayed interactions')
  loaders.SequentialUpdater(interactions, {'s' : outputFld}).update([{'s' : opt.decay(st['strength'], st['length'], divc=coef)} for st in modelInters])

  # rows = arcpy.UpdateCursor(interactions)
  # i = 0
  # for row in rows:
    # # common.debug('%s %s %s' % (row.getValue(strengthFld), modelInters[i], opt.decay(*modelInters[i])))
    # row.setValue(outputFld, opt.decay(*modelInters[i], divc=coef))
    # rows.updateRow(row)
    # i += 1
    
  if reportFileName:
    common.progress('creating report')
    out = (REPORT_TEMPLATE % (interactions, strengthFld, lengthFld, outputFld, count, coef, opt.getB(), opt.getG(), quantileN)) + opt.report()
    opt.writeReport(out, reportFileName)
