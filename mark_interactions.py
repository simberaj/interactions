import common, objects, loaders

with common.runtool(5) as parameters:
  interLayer, query, interStrengthFld, interFromIDFld, interToIDFld = parameters
  inSlots = {'from' : interFromIDFld, 'to' : interToIDFld, 'value' : interStrengthFld}
  outOrdSlots = {'in' : 'ORD_IN', 'out' : 'ORD_OUT'}
  outRelSlots = {'in' : 'RELS_IN', 'out' : 'RELS_OUT'}
  outSigSlots = {'in' : 'SIG_IN', 'out' : 'SIG_OUT'}
  common.progress('loading interactions')
  inter = loaders.InteractionReader(interLayer, inSlots, where=query).read()
  # common.message(inter)
  common.progress('ordering interactions')
  orders = objects.Interactions.transform(inter, 'orders')
  # common.message(orders)
  common.progress('counting relative interaction strength')
  relst = objects.Interactions.transform(inter, 'relativeStrengths')
  # common.message(relst)
  common.progress('selecting significant interactions')
  signif = objects.Interactions.transform(inter, 'significant')
  # common.message(signif)
  common.progress('writing output')
  loaders.InteractionTwosideMarker(interLayer, inSlots, outOrdSlots, where=query).mark(orders)
  loaders.InteractionTwosideMarker(interLayer, inSlots, outRelSlots, where=query).mark(relst)
  loaders.InteractionPresenceMarker(interLayer, inSlots, outSigSlots, where=query).mark(signif)
