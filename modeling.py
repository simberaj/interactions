# Modeling library - contains functions 
import math, operator, common
from numpy import array
try:
  from scipy.optimize import fsolve, fmin
except ImportError:
  raise ImportError, 'modeling tools require an installed SCIPY package'


## INTERACTION CLASS - used in optimization - abstract superclass
class OptimizableInteraction(object):
  def __init__(self, strength, distance):
    if not (strength and float(strength)):
      raise ValueError, 'invalid interaction strength: %s' % strength
    self.strength = float(strength)
    self.distance = float(distance)
  
  def residual(self, b, g):
    return (self.strength - self.theoretical(b, g)) ** 2
  
  def fraction(self, b):
    return NotImplemented
  
  def theoretical(self, b, g):
    return NotImplemented
   
  def real(self):
    return self.strength
  
  @property
  def logdist(self):
    return math.log(self.distance)
  

class GravityInteraction(OptimizableInteraction):
  def __init__(self, strength, distance, massFrom, massTo):
    OptimizableInteraction.__init__(self, strength, distance)
    self.massFrom = float(massFrom)
    self.massTo = float(massTo)
    
  def yLogChar(self): # used for initial logarithmic approximation
    return math.log((self.strength / self.massFrom) / self.massTo)

  def theoretical(self, b, g):
    return g * self.massFrom * self.massTo * (self.distance ** (-b))

  def fraction(self, b):
    return self.massFrom * self.massTo * (self.distance ** (-b))

class GaussianInteraction(OptimizableInteraction):
  def theoretical(self, b, g):
    return g * math.exp(-self.distance ** 2 / b)

  def fraction(self, b):
    return math.exp(-self.distance ** 2 / b)
    
  def yLogChar(self):
    return math.log((self.strength / self.massFrom) / self.massTo)


## OPTIMIZATION CLASS - USED TO DETERMINE THE MODEL PARAMETERS
class Optimizer(object):
  TOLERANCE = 1e-8

  def __init__(self, interactions):
    self.interactions = interactions
    self.b = None
    self.g = None

  # returns a residual sum of square differences between real and modelled interactions
  def decOLS(self, inputs):
    sum = 0
    for inter in self.interactions:
      sum += inter.residual(*inputs)
    return sum

  def theoreticalInteractions(self):
    return [inter.theoretical(self.b, self.g) for inter in self.interactions]
  
  def realInteractions(self):
    return [inter.real() for inter in self.interactions]
  
  def residuals(self, theoretical, real):
    return [theoretical[i] - real[i] for i in range(len(theoretical))]

  def optimizeOLS(self):
    return fmin(self.decOLS, array(self.approx()))

  def getB(self):
    return self.b
  
  def getG(self):
    return self.g

  def report(self, theoretical=None):
    if theoretical is None:
      theoretical = self.theoreticalInteractions()
    theorAvg = sum(theoretical) / float(len(theoretical))
    real = self.realInteractions()
    residuals = self.residuals(theoretical, real)
    return 'REAL INTERACTIONS\n%s\nTHEORETICAL INTERACTIONS\n%s\nRESIDUALS\n%s\n' % (
      self.statReport(real), self.statReport(theoretical), self.statReport(residuals))
  
  def statReport(self, numbers):
    mean = sum(numbers) / float(len(numbers))
    stdev = (sum([res**2 for res in numbers]) / float(len(numbers)))**0.5
    varcoef = (stdev / mean if mean != 0 else 0)
    return '''Mean: %g
Min: %g
Max: %g
Standard deviation: %g
Variation coefficient: %g''' % (mean, min(numbers), max(numbers), stdev, varcoef)

  @staticmethod
  def writeReport(text, fname):
    report(text, fname)
    

class GravityOptimizer(Optimizer):
  # Fits a gravity model in form
  # g * m1 * m2 * d^(-b)
  # where b is the distance decay parameter, g is the scaling factor,
  # m1, m2 masses of the interacting cities and d their distance

  # vraci optimalizacni charakteristiku maximalni verohodnosti pro urceni modelovacich parametru
  def decMLE(self, b):
    inters, logbords, bords, loginters = 0, 0, 0, 0
    for inter in self.interactions:
      inters += inter.strength
      bord = inter.fraction(b)
      logbords += (bord * inter.logdist)
      bords += bord
      loginters += (inter.strength * inter.logdist)
    return (inters * logbords / bords) - loginters

  # vraci logaritmickou aproximaci jako prvni vstupni odhad do optimalizace
  def approx(self):
    xhelps = [inter.logdist for inter in self.interactions]
    yhelps = [inter.yLogChar() for inter in self.interactions]
    yavg = sum(yhelps) / len(yhelps)
    xavg = sum(xhelps) / len(xhelps)
    btops = 0
    bbottoms = 0
    for i in range(len(xhelps)):
      btops += (xhelps[i] - xavg) * (yhelps[i] - yavg)
      bbottoms += (xhelps[i] - xavg) ** 2
    b = -(btops / bbottoms)
    return [b, math.exp(yavg + b * xavg)] 
  
  def countG(self, b):
    strsum = 0
    fracsum = 0
    for inter in self.interactions:
      strsum += inter.strength
      fracsum += inter.fraction(b)
    return strsum / fracsum

  def optimize(self, type='MLE'):
    if type == 'OLS':
      res = self.optimizeOLS()
      self.b = res[0]
      self.g = res[1]
    else:
      self.b = self.optimizeMLE()
      self.g = self.countG(self.b)

  def optimizeMLE(self):
    return float(fsolve(self.decMLE, self.approx()[0], xtol=self.TOLERANCE))


class GaussianOptimizer(Optimizer):
  # Fits a Gaussian curve to the interactions in form
  # f = g * e ^ (-d^2 / b)
  # where b is the bandwidth and g is the scaling factor.
  
  # creates group interactions from raw interactions by grouping into quantiles and assigning their sum
  # primarily for calculating distance decay
  @classmethod
  def fromData(cls, data, qnum=20):
    # expects data to contain 2-tuples of (strength, length)
    count = len(data)
    # compute number of quantiles
    maxQ = len(data) / 10
    qnum = qnum if qnum < maxQ else maxQ
    # sort the data
    data = sorted(data, key=operator.itemgetter('strength'))
    # compute quantile strength sums and their mean length as new interactions
    interactions = []
    fromBreak = 0
    for i in range(1, qnum):
      toBreak = int(round(i * count / qnum))
      qsum = sum([item['strength'] for item in data[fromBreak:toBreak]])
      qmid = sum([item['length'] for item in data[fromBreak:toBreak]]) / (toBreak - fromBreak)
      interactions.append(GaussianInteraction(qsum, qmid))
      fromBreak = toBreak
    return cls(interactions)

  # initial approximation of the curve by solving the parameter values analytically from two
  # values of the curve
  def approx(self):
    # two approximate points to fit the gaussian curve
    inter1 = self.interactions[len(self.interactions) // 4]
    inter2 = self.interactions[len(self.interactions) // 2]
    # logarithmic approximation of bandwidth
    b = (inter1.distance ** 2 - inter2.distance ** 2) / (math.log(inter2.strength) - math.log(inter1.strength))
    return [b, inter1.strength / inter1.fraction(b)]
  
  def optimize(self):
    self.b, self.g = self.optimizeOLS()
  
  def decay(self, strength, distance, divc=1):
    return strength * math.exp(-(distance ** 2) / (self.b * divc))
    
def report(text, fname):
  common.progress('saving report')
  try:
    with open(fname, 'w') as outfile:
      outfile.write(text.encode('utf8'))
  except (IOError, OSError, UnicodeEncodeError):
    common.warning('Report output failed.')
