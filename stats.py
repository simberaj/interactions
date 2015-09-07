def median(numbers):
  half = int(len(numbers) / 2)
  if len(numbers) % 2 == 0:
    return (numbers[half - 1] + numbers[half]) / 2.0
  else:
    return numbers[half]

def genMode(masses, qsize=7):
  if len(masses) < qsize:
    return min(masses)
  masses.sort()
  # count = len(masses)
  modes = []
  for init in range(qsize):
    i = 0
    minI = 0
    minWidth = masses[-1] + 1 # effectively positive infinity
    while (qsize * i - init) < len(masses):
      low = max(0, qsize * i - init)
      high = min(len(masses) - 1, qsize * (i+1) - init - 1)
      width = (masses[high] - masses[low]) / float(high - low + 1)
      # print init, low, high, width
      if width < minWidth and (high - low) != 0:
        minI = i
        minWidth = width
      i += 1
    low = max(0, qsize * minI - init)
    high = min(len(masses), qsize * (minI + 1) - init)
    # print low, high, sum(masses[low:high]) / float(high - low)
    modes.append(sum(masses[low:high]) / float(high - low))
  modes.sort()
  # print modes
  return median(modes)
  # modeI = int((narrowestLeft + narrowestRight) * 0.5)
  # # common.debug('%s: %s' % (qnum, masses[modeI]))
  # return masses[modeI]

# def genModeOld(masses, qnum=15):
  # '''Calculates a generalised mode of a list as an average of the narrowest quantile interval.'''
  # masses.sort()
  # count = len(masses)
  # prevBreak = 0
  # minWidth = masses[-1] + 1
  # minI = 1
  # for i in range(1, qnum):
    # curBreak = masses[int(round(i * count / qnum))]
    # width = curBreak - prevBreak
    # if width < minWidth:
      # minWidth = width
      # minI = i
  # narrowestLeft = int(round((minI-1) * count / float(qnum)))
  # narrowestRight = int(round(minI * count / float(qnum)))
  # modeI = int((narrowestLeft + narrowestRight) * 0.5)
  # # common.debug('%s: %s' % (qnum, masses[modeI]))
  # return masses[modeI]

# def genModeEqualised(cls, masses, minI=6, maxI=20):
  # '''Calculates a generalised mode as an average of multiple generalised modes at different quantile counts.'''
  # if len(masses) <= 3:
    # return min(masses) # of no use to compute anything... too little data
  # masses.sort()
  # # common.debugMode = True
  # # common.debug(masses)
  # # prevent too many or too little intervals for too little data
  # maxI = common.inBounds(maxI, 3, len(masses) / 2)
  # minI = common.inBounds((minI - 1), 1, (maxI - 1))
  # if minI == maxI: maxI += 1
  # lowest10 = 0 # int(len(masses) * 0.1) # exclude lowest 10 percent
  # return sum(cls.generalisedMode(masses[lowest10:], n) for n in range(minI, maxI)) / float(maxI - minI)


def jenksBreaks(dataList, numClass):
  dataList.sort()
  lowerLims = [[0] * (numClass + 1) for i in range(len(dataList) + 1)]
  varCombinations = [[0] * (numClass + 1) for i in range(len(dataList) + 1)]
  # initial setup
  for i in range(1, numClass + 1):
    lowerLims[1][i] = 1
    varCombinations[1][i] = 0
    for j in range(2, len(dataList) + 1):
      varCombinations[j][i] = float('inf')
  varcoef = 0.0
  for l in range(2, len(dataList) + 1):
    sd = 0.0
    var = 0.0
    for m in range(l):
      index = l - m - 1
      val = float(dataList[index])
      var += val * val
      sd += val
      varcoef = var - (sd * sd) / (m + 1)
      if index != 0:
        for j in range(2, numClass + 1):
          if varCombinations[l][j] >= (varcoef + varCombinations[index][j - 1]):
            lowerLims[l][j] = index + 1
            varCombinations[l][j] = varcoef + varCombinations[index][j - 1]
    lowerLims[l][1] = 1
    varCombinations[l][1] = varcoef
  k = len(dataList)
  kclass = [0] * numClass + [dataList[-1]]
  countNum = numClass
  while countNum > 1:
    kclass[countNum - 1] = dataList[int((lowerLims[k][countNum]) - 2)]
    k = int((lowerLims[k][countNum] - 1))
    countNum -= 1
  return kclass

if __name__ == '__main__':
  test = [1, 2, 4, 5, 5, 6, 6, 7, 8, 9, 11, 13, 16, 20, 24, 30, 45, 80]
  # test = [1, 2, 2, 3, 8, 9, 10, 12, 13, 20, 22, 23, 25, 27, 50, 51, 52, 53]
  print test
  for i in range(5, 9):
    print 'Generalised mode (qsize %i): ' % i, genMode(test, i)
  print 'Jenks breaks: ', jenksBreaks(test, 4)