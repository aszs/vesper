#:copyright: Copyright 2009-2010 by the Vesper team, see AUTHORS.
#:license: Dual licenced under the GPL or Apache2 licences, see LICENSE.
@Action
def testaction(kw, retval):
    if kw._name != 'foo':
        return retval
    e = Exception('not found')
    e.errorCode = 404
    raise e

originalCommit = None
badCommitCalled = False
@Action
def testInTransactionAction(kw, retval):
    if kw._name != 'errorInCommit':
        return retval
    dataStore = kw.__server__.defaultStore
    dataStore.add({"id" : "test", "test" : 'hello!'})
    def badCommit(*args, **kw):
        global badCommitCalled
        badCommitCalled = True 
        raise RuntimeError("this error inside commit")
        
    global originalCommit    
    originalCommit = dataStore.model.commit
    from vesper.data import DataStore
    if isinstance(dataStore.model, DataStore.ModelWrapper): 
        dataStore.model.model.commit = badCommit        
    else:
        dataStore.model.commit = badCommit 
    return 'success'

@Action
def errorhandler(kw, retval):
    #print 'in error handler', kw['_errorInfo']['errorCode'], 'badCommit', badCommitCalled, kw.__server__.defaultStore.model
    if originalCommit:
        kw.__server__.defaultStore.model.commit = originalCommit        

    if kw['_errorInfo']['errorCode'] == 404:
        kw['_responseHeaders']['_status'] = 404
        return '404 not found'
    else:
        kw['_responseHeaders']['_status'] = 503
        return 'badCommit: %s' % badCommitCalled  

actions = {         
        'http-request' : [  testInTransactionAction, testaction ],
        'http-request-error': [ errorhandler ]
        }

createApp(actions=actions)
