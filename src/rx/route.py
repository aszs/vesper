from raccoon import *
from rx.utils import defaultattrdict
import os.path
from urllib import url2pathname
import logging
log = logging.getLogger("server")

from routes import Mapper
route_map = Mapper()
route_map.minimization = False

# Routes mapper maintains a route cache that must be regenerated when
# new routes are added
_routemap_dirty = True

def Route(path, route_map=route_map, **vars):
    def _route(func):
        global _routemap_dirty
        if not isinstance(func, Action):
            func = Action(func)
        route_map.connect(None, path, controller=func)
        # print "mapping %s -> %s" % (path, str(func))
        _routemap_dirty = True
    return _route

def gensequence(kw, default=None):
    "Yields an Action.  This is a generator purely due to requirements in the Action code"
    global _routemap_dirty    
    if _routemap_dirty:
        # print "generating routemap"
        route_map.create_regs()
        _routemap_dirty = False
    
    request_url = kw['_name']
    # print "matching on:'%s' default:%s" % (request_url, str(default))
    r = route_map.match(request_url)
    if r:
        kw['urlvars'] = r # XXX should probably strip 'action' & 'controller'
        yield r['controller']
    elif default:
        yield default

@Action
def servefile(kw, retval):
    #value = kw
    #for n in name.split('.'):
    #    value = value[n]
    return _servefile(kw,retval,kw._name)

def _servefile(kw, retval, uri):
    path = url2pathname(uri)
    unauthorized = False
    server = kw.__server__
    for prefix in server.static_path:            
        filepath = os.path.join(prefix.strip(), path)        
        #print 'filepath', filepath
        #check to make sure the path url wasn't trying to sneak outside the path (e.g. by using "..")
        if server.SECURE_FILE_ACCESS:
            if not os.path.abspath(filepath).startswith(os.path.abspath(prefix)):
                unauthorized = True                
                continue
        unauthorized = False
        if os.path.exists(filepath):
            return file(filepath)

    #if unauthorized:
    #    raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized')                 
    return retval #not found

@Action #Route(default=True)
def servetemplate(kw, retval):
    path = kw._name
    template = kw.__server__.template_loader.get_template(path)
    if template:
        return template.render(params=kw._params, 
                        urlvars=kw.get('urlvars',{}), 
                        request=kw, 
                        config=kw.__server__.config,
                        server=kw.__server__, 
                        db=kw.__server__.dataStore)
    else:
        return retval
