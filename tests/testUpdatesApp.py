@Action
def updateAction(kw, retval):
    '''
    Run this action every request but should only add content the first time
    '''
    sjson = [{ 'id' : 'a_resource',
       'label' : 'foo',
      'comment' : 'page content.'
    }]
    kw['__server__'].domStore.update(sjson)
    return retval

@Action
def queryAction(kw, retval):
    query = "{comment:* where(label='%s')}" % kw['_name'] #XXX qnames are broken         
    result = list(kw['__server__'].domStore.query(query))
    #print result
        
    template = '<html><body>%s</body></html>'
    if result:
        return template % result[0]['comment']
    else:
        kw['_status'] = 404
        return template % 'not found!'
                                        
actions = { 'http-request' : [updateAction, queryAction]
        }
