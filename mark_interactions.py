import common, objects, loaders

with common.runtool(5) as parameters:
  interLayer, query, interFromIDFld, interToIDFld, interStrengthFld = parameters
  inSlots = {'from' : interFromIDFld, 'to' : interToIDFld, 'value' : interStrengthFld}
  outOrdSlots = {'in' : 'ORD_IN', 'out' : 'ORD_OUT'}
  outRelSlots = {'in' : 'RELS_IN', 'out' : 'RELS_OUT'}
  outSigSlots = {'in' : 'SIG_IN', 'out' : 'SIG_OUT'}
  common.progress('loading interactions')
  inter = loaders.InteractionReader(interLayer, inSlots, where=query).read()
  common.progress('ordering interactions')
  orders = objects.Interactions.transform(inter, 'orders')
  common.progress('counting relative interaction strength')
  relst = objects.Interactions.transform(inter, 'relativeStrengths')
  common.progress('selecting significant interactions')
  signif = objects.Interactions.transform(inter, 'significant')
  common.progress('writing output')
  loaders.InteractionTwosideMarker(interLayer, inSlots, outOrdSlots, where=query).mark(orders)
  loaders.InteractionTwosideMarker(interLayer, inSlots, outRelSlots, where=query).mark(relst)
  loaders.InteractionPresenceMarker(interLayer, inSlots, outSigSlots, where=query).mark(signif)
