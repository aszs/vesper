#:copyright: Copyright 2009-2010 by the Vesper team, see AUTHORS.
#:license: Dual licenced under the GPL or Apache2 licences, see LICENSE.
@Action
def updateAction(kw, retval):
    '''
    Run this action every request but should only add content the first time
    '''
    pjson = [{ 'id' : 'a_resource',
       'label' : 'foo',
      'comment' : 'page content.'
    }]
    kw['__server__'].defaultStore.update(pjson)
    return retval

@Action
def queryAction(kw, retval):
    query = "{comment where(label='%s')}" % kw['_name']
    result = kw['__server__'].defaultStore.query(query)
        
    template = '<html><body>%s</body></html>'
    if result:
        return template % result[0]['comment']
    else:
        kw['_status'] = 404
        return template % 'not found!'

@Action 
def recordUpdates(kw, retval):
    kw['__server__'].updateResults = kw._dbchanges and kw._dbchanges[0] or None

@Action
def testLoadModelHook(kw, retVal):
    kw.__server__.loadModelHookCalled = True
    return retVal
             
actions = { 'http-request' : [updateAction, queryAction],
'after-commit' : [recordUpdates],
'load-model':[testLoadModelHook]
}

createApp(actions=actions, save_history='split')
