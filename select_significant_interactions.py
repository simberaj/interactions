## IMPORT MODULES
import sys # basic
import traceback
sys.path.append('.')
import common, objects, loaders

if __name__ == '__main__':
  try:
    common.progress('loading tool parameters')
    # common.message(common.parameters(14))
    interLayer, query, interFromIDFld, interToIDFld, interStrengthFld = common.parameters(5)
    inSlots = {'from' : interFromIDFld, 'to' : interToIDFld, 'value' : interStrengthFld}
    outSlots = {'in' : 'SIG_IN', 'out' : 'SIG_OUT'}
    common.progress('loading interactions')
    inter = loaders.InteractionReader(interLayer, slots, where=query).read()
    common.progress('selecting significant interactions')
    signif = objects.Interactions.selectSignificant(inter)
    common.progress('writing output')
    loaders.InteractionPresenceMarker(interLayer, inSlots, outSlots, where=query).mark(signif)
    common.done()
  except:
    common.message(traceback.format_exc())
    raise
