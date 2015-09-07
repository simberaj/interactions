import arcpy, common

strLayer = 'tmp_i095'
relLayer = 'tmp_i043'

with common.runtool(7) as parameters:
  interLayer, strengthFld, lengthFld, minStrengthStr, minRelStrengthStr, maxLengthStr, output = parameters
  if minStrengthStr or maxLengthStr:
    queries = []
    if minStrengthStr:
      common.progress('assembling absolute strength exclusion')
      minStrength = common.toFloat(minStrengthStr, 'minimum absolute interaction strength')
      queries.append(common.query(interLayer, '[%s] >= %g', strengthFld, minStrength))
    if maxLengthStr:
      common.progress('assembling absolute length exclusion')
      maxLength = common.toFloat(maxLengthStr, 'maximum absolute interaction length')
      queries.append(common.query(interLayer, '[%s] <= %g', lengthFld, maxLength))
    common.selection(interLayer, strLayer, ' OR '.join(queries))
  else:
    strLayer = interLayer
  if minRelStrengthStr:
    common.progress('performing relative strength exclusion')
    minRelStrength = common.toFloat(minRelStrengthStr, 'minimum relative interaction strength')
    relQuery = common.query(interLayer, '[%s] > 0 AND ([%s] / [%s] * 1000) >= %g', lengthFld, strengthFld,
      lengthFld, minRelStrength)
    common.select(strLayer, relLayer, relQuery)
  else:
    relLayer = strLayer
  common.progress('counting selected interactions')
  common.message('%i interactions selected.' % common.count(relLayer))
  common.progress('writing output')
  common.copy(relLayer, output)