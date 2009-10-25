"""
    DOMStore classes used by Raccoon.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx import RxPath, transactions
import StringIO, os, os.path
import logging
from rx.utils import debugp

def _toStatements(contents):
    import sjson
    if not contents:
        return [], None
    if isinstance(contents, (list, tuple)):
        if isinstance(contents[0], (tuple, RxPath.BaseStatement)):
            return contents, None #looks like a list of statements
    #assume sjson:
    return sjson.tostatements(contents), contents

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
            
class BasicStore(DomStore):

    def __init__(self, requestProcessor, modelFactory=None,
                 schemaFactory=RxPath.defaultSchemaClass,                 
                 STORAGE_PATH ='',
                 STORAGE_TEMPLATE='',
                 APPLICATION_MODEL='',
                 transactionLog = '',
                 saveHistory = False,
                 VERSION_STORAGE_PATH='',
                 versionModelFactory=None,
                 storageTemplateOptions=None,
                 DOM_CHANGESET_HOOK=None,
                 branchId = '0A', **kw):
        '''
        modelFactory is a RxPath.Model class or factory function that takes
        two parameters:
          a location (usually a local file path) and iterator of Statements
          to initialize the model if it needs to be created
        '''
        self.requestProcessor = requestProcessor
        self.modelFactory = modelFactory or RxPath.TransactionFileModel
        self.versionModelFactory = versionModelFactory or modelFactory or RxPath.IncrementalNTriplesFileModel
        self.schemaFactory = schemaFactory 
        self.APPLICATION_MODEL = APPLICATION_MODEL        
        self.STORAGE_PATH = STORAGE_PATH        
        self.VERSION_STORAGE_PATH = VERSION_STORAGE_PATH
        self.STORAGE_TEMPLATE = STORAGE_TEMPLATE
        self.transactionLog = transactionLog
        self.saveHistory = saveHistory
        self.storageTemplateOptions = storageTemplateOptions
        self.branchId = branchId
        self.changesetHook = DOM_CHANGESET_HOOK
            
    def loadDom(self):        
        requestProcessor = self.requestProcessor
        self.log = logging.getLogger("domstore." + requestProcessor.appName)

        #normalizeSource = getattr(self.modelFactory, 'normalizeSource',
        #                                        DomStore._normalizeSource)
        #source is the data source for the store, usually a file path
        #source = normalizeSource(self, requestProcessor, self.STORAGE_PATH)
        source = self.STORAGE_PATH
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
            from rx import RxPathGraph
            self.model = self.graphManager = RxPathGraph.MergeableGraphManager(model, 
                historyModel, requestProcessor.MODEL_RESOURCE_URI, lastScope, self.branchId)
        else:
            self.graphManager = None
        
        if self.changesetHook:
            assert self.saveHistory, "replication requires saveHistory to be on"
            self.model.notifyChangeset = self.changesetHook
        
        #set the schema (default is no-op)
        self.schema = self.schemaFactory(self.model)
        #XXX need for graphManager?:
        #self.schema.setEntailmentTriggers(self._entailmentAdd, self._entailmentRemove)
        if isinstance(self.schema, RxPath.Model):
            self.model = self.schema

        #hack!
        if self.storageTemplateOptions and self.storageTemplateOptions.get(
                                            'generateBnode') == 'counter':
            model.bnodePrefix = '_:'

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
                        requestProcessor.MODEL_RESOURCE_URI, scope=initCtxUri, 
                        options=self.storageTemplateOptions) 
                
        #if we're using a separate store to hold the change history, load it now
        #(it's called delmodel because it only stores removals as the history 
        #is recorded soley as adds and removes)
        if self.VERSION_STORAGE_PATH:
            normalizeSource = getattr(self.versionModelFactory, 
                    'normalizeSource', DomStore._normalizeSource)
            versionStoreSource = normalizeSource(self, requestProcessor,
                                                 self.VERSION_STORAGE_PATH)
            revisionModel = self.versionModelFactory(source=versionStoreSource,
                                                defaultStatements=[])
        else:
            revisionModel = None

        #open or create the model (the datastore)
        #if savehistory is on and we are loading a store that has the entire 
        #change history (e.g. we're loading the transaction log) we also load 
        #the history into a separate model
        #
        #note: to override loadNtriplesIncrementally, set this attribute
        #on your custom modelFactory
        if self.saveHistory and getattr(
                self.modelFactory, 'loadNtriplesIncrementally', False):
            if not revisionModel:
                revisionModel = RxPath.TransactionMemModel()
            dmc = RxPathGraph.DeletionModelCreator(revisionModel)
            model = self.modelFactory(source=source,
                    defaultStatements=defaultStmts, incrementHook=dmc)
            lastScope = dmc.lastScope        
        else:
            model = None
            lastScope = None
        
        return model, defaultStmts, revisionModel, lastScope

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
    
    def join(self, txnService):
        if hasattr(txnService.state, 'kw'):
            txnCtxtResult = self.getTransactionContext()
            txnService.state.kw['__current-transaction'] = txnCtxtResult
        return super(BasicStore,self).join(txnService)
    
    def add(self, adds):
        '''
        Adds data to the store.

        `adds`: A list of either statements or sjson conforming dicts
        '''
        self.join(self.requestProcessor.txnSvc)
        stmts, jsonrep = _toStatements(adds)
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
        return stmts
        
    def remove(self, removes):
        '''

        Removes data from the store.
        `removes`: A list of either statements or sjson conforming dicts
        '''
        self.join(self.requestProcessor.txnSvc)
        stmts, jsonrep = _toStatements(removes)

        if self.removeTrigger and stmts:
            self.removeTrigger(stmts, jsonrep)

        self.model.removeStatements(stmts)

    def update(self, updates):
        '''
        Update the store by either adding or replacing the property value pairs
        given in the update, depending on whether or not the pair currently 
        appears in the store.

        See also `replace`.

        `updates`: A list of either statements or sjson conforming dicts
        '''
        return self.updateAll(updates, [])

    def replace(self, replacements):
        '''
        Replace the given objects in the store. Unlike `update` this method will
        remove properties in the store that aren't specified.
        Also, if the data contains json object and an object has no properties
        (just an `id` property), the object will be removed.

        See also `update` and `updateAll`.

        `replacements`: A list of either statements or sjson conforming dicts
        '''
        return self.updateAll([], replacements)

    def updateAll(self, update, replace, removedResources=None):
        '''
        Add, remove, update, or replace resources in the store.

        `update`: A list of either statements or sjson conforming dicts that will
        be processed with the same semantics as the `update` method.
        
        `replace`: A list of either statements or sjson conforming dicts that will
        be processed with the same semantics as the `replace` method.
        
        `removedResources`: A list of ids of resources that will be removed 
        from the store.
        '''
        self.join(self.requestProcessor.txnSvc)

        removedResources = set(removedResources or [])

        updateStmts, ujsonrep = _toStatements(update)
        replaceStmts, replaceJson = _toStatements(replace)
        if replaceJson:
            for o in replaceJson:
                #the object is empty so make it for removal
                #we need to do this here because empty objects won't show up in
                #replaceStmts
                if len(o) == 1:
                    removeid = o['id']
                    removedresources.add(removeid)
        
        updateDom = RxPath.RxPathDOMFromStatements(updateStmts + replaceStmts)
        srcstmts = []
        resources = set()
        replaceResources = set(s[0] for s in replaceStmts)

        for subjectNode in updateDom.childNodes:
            subject = subjectNode.uri
            resources.add(subject)
            if subject in replaceResources:
                srcstmts.extend( self.model.getStatements(subject) )
            else:                
                subjectStmts = subjectNode.getModelStatements()
                predicates = set(stmt.predicate for stmt in subjectStmts)
                for prop in predicates:                                        
                    propstmts = self.model.getStatements(subject, prop)
                    srcstmts.extend( propstmts )

        srcDom = RxPath.RxPathDOMFromStatements(srcstmts)
        newStatements, removedNodes = RxPath.mergeDOM(srcDom, updateDom, resources)
        
        removals = []
        if removedResources:            
            for subject in removedResources:
                removals.extend( self.model.getStatements(subject) )

        for node in removedNodes:
            stmts = node.getModelStatements()
            #for s in stmts:
            #    if s.object is bnode:
            #        bnode
            removals.extend( stmts )

        self.remove(removals)        
        return self.add(newStatements), removals

    def query(self, query, bindvars=None, explain=None, debug=False, **kw):
        import jql
        return jql.getResults(query, self.model,bindvars,explain,debug)

    def merge(self,changeset): 
        from rx import RxPathGraph
        assert isinstance(self.graphManager, RxPathGraph.MergeableGraphManager)
        
        #graphManager.merge() needs special transaction logic since we don't 
        #want the transaction metadata that the standard commit creates and saves
        class Merger(transactions.TransactionParticipant):
            def __init__(self, graphManager):
                self.graphManager = graphManager
                
            def merge(self, requestProcessor, changeset):
                self.join(requestProcessor.txnSvc)
                return self.graphManager.merge(changeset)
                                
            def commitTransaction(self, txnService):
                if self.graphManager.revisionModel != self.graphManager.managedModel:
                    self.graphManager.revisionModel.commit(**txnService.getInfo())     
                self.graphManager.managedModel.commit(**txnService.getInfo())
            
            def abortTransaction(self, txnService):                    
                self.graphManager.managedModel.rollback()
                if self.graphManager.revisionModel != self.graphManager.managedModel:
                    self.graphManager.revisionModel.rollback()
        
        return Merger(self.graphManager).merge(self.requestProcessor, changeset)
