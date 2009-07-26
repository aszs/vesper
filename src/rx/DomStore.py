"""
    DOMStore classes used by Raccoon.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx import RxPath, transactions
import StringIO, os, os.path
import logging

def _toStatements(contents):
    import sjson
    if not contents:
        return [], None
    if isinstance(contents, (list, tuple)):
        if isinstance(contents, (tuple, BaseStatement)):
            return contents, None #looks like a list of statements
    #assume sjson:
    sjson.tostatements(contents), contents

class DomStore(transactions.TransactionParticipant):
    '''
    Abstract interface for DomStores
    '''
    log = logging.getLogger("domstore")

    #impl. must expose the DOM as a read-only attribute named "dom"
    dom = None

    addTrigger = None
    removeTrigger = None
    newResourceTrigger = None

    def __init__(requestProcessor, **kw):
        pass
    
    def loadDom(self, location, defaultDOM):
        ''' 
        Load the DOM located at location (a filepath).
        If location does not exist create a new DOM that is a copy of 
        defaultDOM, a file-like of appropriate type
        (e.g. an XML or RDF NTriples file).
        '''
        self.log = logging.getLogger("domstore." + requestProcessor.appName)
                        
    def commitTransaction(self, txnService):
        pass

    def abortTransaction(self, txnService):
        pass

    def getStateKey(self):
        '''
        Returns the a hashable object that uniquely identifies the current state of DOM.
        Used for caching.
        If this is not implemented, it should raise KeyError (the default implementation).
        '''
        raise KeyError

    def getTransactionContext(self):
        return None
        
    def _normalizeSource(self, requestProcessor, path):
        #if source was set on command line, override config source
        if requestProcessor.source:            
            source = requestProcessor.source
        else:
            source = path

        if not source:
            self.log.warning('no model path given and STORAGE_PATH'
                             ' is not set -- model is read-only.')            
        elif not os.path.isabs(source):
            #XXX its possible for source to not be file path
            #     -- this will break that
            source = os.path.join( requestProcessor.baseDir, source)
        return source
            
class BasicDomStore(DomStore):

    def __init__(self, requestProcessor, modelFactory=RxPath.IncrementalNTriplesFileModel,
                 schemaFactory=RxPath.defaultSchemaClass,                 
                 STORAGE_PATH ='',
                 STORAGE_TEMPLATE='',
                 APPLICATION_MODEL='',
                 transactionLog = '',
                 saveHistory = False,
                 VERSION_STORAGE_PATH='',
                 versionModelFactory=None, **kw):
        '''
        modelFactory is a RxPath.Model class or factory function that takes
        two parameters:
          a location (usually a local file path) and iterator of Statements
          to initialize the model if it needs to be created
        '''
        self.requestProcessor = requestProcessor
        self.modelFactory = modelFactory
        self.versionModelFactory = versionModelFactory or modelFactory
        self.schemaFactory = schemaFactory 
        self.APPLICATION_MODEL = APPLICATION_MODEL        
        self.STORAGE_PATH = STORAGE_PATH        
        self.VERSION_STORAGE_PATH = VERSION_STORAGE_PATH
        self.STORAGE_TEMPLATE = STORAGE_TEMPLATE
        self.transactionLog = transactionLog
        self.saveHistory = saveHistory
            
    def loadDom(self):        
        requestProcessor = self.requestProcessor
        self.log = logging.getLogger("domstore." + requestProcessor.appName)

        normalizeSource = getattr(self.modelFactory, 'normalizeSource',
                                                DomStore._normalizeSource)
        #source is the data source for the store, usually a file path
        source = normalizeSource(self, requestProcessor, self.STORAGE_PATH)
        
        model, defaultStmts, historyModel, lastScope = self.setupHistory(source)
        if not model:
            #setupHistory didn't initialize the store, so do it now
            #modelFactory will load the store specified by `source` or create
            #new one at that location and initializing it with `defaultStmts`
            model = self.modelFactory(source=source, 
                                            defaultStatements=defaultStmts)

        #if there's application data (data tied to the current revision
        #of your app's implementation) include that in the model
        if self.APPLICATION_MODEL:
            from rx.RxPathGraph import APPCTX #'context:application:'
            stmtGen = RxPath.parseRDFFromString(self.APPLICATION_MODEL, 
                requestProcessor.MODEL_RESOURCE_URI, scope=APPCTX) 
                                        
            appmodel = RxPath.MemModel(stmtGen)
            #XXX MultiModel is not very scalable -- better would be to store 
            #the application data in the model and update it if its difference 
            #from what's stored (of course this requires a context-aware store)
            model = RxPath.MultiModel(model, appmodel)
        
        #turn on update logging if a log file is specified, which can be used to 
        #re-create the change history of the store
        if self.transactionLog:
            model = RxPath.MirrorModel(model, RxPath.IncrementalNTriplesFileModel(
                self.transactionLog, []) )

        self.model = model

        if self.saveHistory:
            self.model = self.graphManager = RxPathGraph.NamedGraphManager(model, 
                historyModel, requestProcessor.MODEL_RESOURCE_URI, lastScope)
        else:
            self.graphManager = None
        
        #set the schema (default is no-op)
        self.schema = self.schemaFactory(self.model)
        #XXX need for graphManager?:
        #self.schema.setEntailmentTriggers(self._entailmentAdd, self._entailmentRemove)
        if isinstance(self.schema, RxPath.Model):
            self.model = self.schema

    def setupHistory(self, source):
        requestProcessor = self.requestProcessor
        if self.saveHistory:
            #if we're going to be recording history we need a starting context uri
            from rx import RxPathGraph
            initCtxUri = RxPathGraph.getTxnContextUri(requestProcessor.MODEL_RESOURCE_URI, 0)
        else:
            initCtxUri = ''
        
        #data used to initialize a new store
        defaultStmts = RxPath.parseRDFFromString(self.STORAGE_TEMPLATE, 
                        requestProcessor.MODEL_RESOURCE_URI, scope=initCtxUri) 
                
        #if we're using a separate store to hold the change history, load it now
        #(it's called delmodel because it only stores removals as the history 
        #is recorded soley as adds and removes)
        if self.VERSION_STORAGE_PATH:
            normalizeSource = getattr(self.versionModelFactory, 
                    'normalizeSource', DomStore._normalizeSource)
            versionStoreSource = normalizeSource(self, requestProcessor,
                                                 self.VERSION_STORAGE_PATH)
            delmodel = self.versionModelFactory(source=versionStoreSource,
                                                defaultStatements=[])
        else:
            delmodel = None

        #open or create the model (the datastore)
        #if savehistory is on and we are loading a store that has the entire 
        #change history (e.g. we're loading the transaction log) we also load 
        #the history into a separate model
        #
        #note: to override loadNtriplesIncrementally, set this attribute
        #on your custom modelFactory
        if self.saveHistory and getattr(
                self.modelFactory, 'loadNtriplesIncrementally', False):
            if not delmodel:
                delmodel = RxPath.MemModel()
            dmc = RxPathGraph.DeletionModelCreator(delmodel)            
            model = self.modelFactory(source=source,
                    defaultStatements=defaultStmts, incrementHook=dmc)
            lastScope = dmc.lastScope        
        else:
            model = None
            lastScope = None
            
        return model, defaultStmts, delmodel, lastScope

    def isDirty(self, txnService):
        '''return True if this transaction participant was modified'''    
        return txnService.state.additions or txnService.state.removals
        
    def commitTransaction(self, txnService):
        self.model.commit(**txnService.getInfo())

    def abortTransaction(self, txnService):        
        if not self.isDirty(txnService):
            return

        #from rx import MRUCache
        #key = self.dom.getKey()

        self.model.rollback()
                        
        #if isinstance(key, MRUCache.InvalidationKey):
        #    if txnService.server.actionCache:
        #        txnService.server.actionCache.invalidate(key)

    def getTransactionContext(self):
        if self.graphManager:
            return self.graphManager.getTxnContext() #return a contextUri
        return None
        
    def add(self, updates):
        '''
        Takes a list of either statements or sjson conforming dicts
        '''
        self.join(self.requestProcessor.txnSvc)
        stmts, jsonrep = _toStatements(updates)
        resources = set()
        newresources = []
        for s in stmts:
            if self.newResourceTrigger:
                subject = s[0]
                if subject not in resources:
                    resource.update(subject)
                    if not self.model.filter(subject=subject, hints=dict(limit=1)): 
                        newresources.append(subject)

        if self.newResourceTrigger and newresources:  
            self.newResourceTrigger(newresources)
        if self.addTrigger and stmts:
            self.addTrigger(stmts, jsonrep)

        self.model.addStatements(stmts)
        
    def remove(self, removals):    
        '''
        Takes a list of either statements or sjson conforming dicts
        '''
        #XXX to remove an object you have to explicitly list all the properties to remove 
        #do we need a ways to remove an object just specifying id
        self.join(self.requestProcessor.txnSvc)
        stmts, jsonrep = _toStatements(removals)
        if self.removeTrigger and stmts:
            self.removeTrigger(stmts, jsonrep)

        self.model.removeStatements(stmts)

    def update(self, replacements, removedresources, deleteprops=False):
        '''
        `deleteprops`: either bool
        ''' 
        deletepropstest = True               
        try:
            '' in deleteprops
        except TypeError:
            deletepropstest = False
        
        removals = []
        for res in replacements:
            if (deletepropstest and res in deleteprops) or deleteprops:
               removals.extend( list(self.model.getStatements(res)) )
            else:
                #xxx what about lists?
                for prop in res:
                    removals.extend( list(self.model.getStatements(res, prop)) )
        
        
    def query(self, query):
        import jql
        return jql.runQuery(query, self.model)
        