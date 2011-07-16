#:copyright: Copyright 2009-2010 by the Vesper team, see AUTHORS.
#:license: Dual licenced under the GPL or Apache2 licences, see LICENSE.
"""
    vesper.data.DataStore
    =====================
    
    This module defined the high-level public interface to a data store.
"""
import StringIO, os, os.path
import logging
import time

from vesper.data import base, transactions
from vesper.data.base import graph as graphmod # avoid aliasing some local vars
from vesper.data.store.basic import MemStore, FileStore, IncrementalNTriplesFileStoreBase
from vesper.utils import debugp, flatten, defaultattrdict
from vesper.data.base.utils import OrderedModel
from vesper.data.base.schema import defaultSchemaClass

from vesper import pjson

class DataStoreError(Exception):
    '''Base DataStore error'''

def _toStatements(contents, **kw):
    if not contents:
        return [], contents, []
    if isinstance(contents, (list, tuple)):
        if isinstance(contents[0], (tuple, base.BaseStatement)):
            return contents, None, [] #looks like a list of statements
        
    #at this point assume contents is pjson
    kw['setBNodeOnObj']=True #set this option so generated ids are visible
    stmts, emptyobjs = pjson.Parser(**kw).to_rdf(contents)
    return stmts, contents, emptyobjs

class DataStore(transactions.TransactionParticipant): # XXX this base class can go away
    '''
    Abstract interface for DataStores
    '''
    log = logging.getLogger("datastore")

    addTrigger = None
    removeTrigger = None
    newResourceTrigger = None

    def __init__(requestProcessor, **kw):
        pass
    
    def load(self):
        self.log = logging.getLogger("datastore." + requestProcessor.app_name)
                        
    def commitTransaction(self, txnService):
        pass

    def abortTransaction(self, txnService):
        pass

    def getStateKey(self):
        '''
        Returns the a hashable object that uniquely identifies the current state of this datastore.
        Used for caching.
        If this is not implemented, it should raise KeyError (the default implementation).
        '''
        raise KeyError

    def getTransactionContext(self):
        return None
        
    def _normalizeSource(self, requestProcessor, source):
        if not source:
            self.log.warning('no model path given and storage_path'
                             ' is not set -- model is read-only.')            
        elif not os.path.isabs(source):
            #XXX its possible for source to not be file path
            #     -- this will break that
            source = os.path.join( requestProcessor.baseDir, source)
        return source
            
class BasicStore(DataStore):
    '''
    Provides transacted operations on the underlying data store.
    '''
    
    #if simpleEmbeddingSemantics = True then update operations will look for
    #identifiers generated by the pjson parser that indicate the object is an 
    #anonymous embedded object, allowing the store to make the assumption the 
    #embedded objects are just referenced by one property (at a time).
    #This enables the following update semantics:
    #1. when updating a prop by replacing one embedded object with another, 
    #perserve the old embedded object's identity and only commit the changes.
    #2. when removing a prop with an embedded object that's not being replaced 
    #by another embedded object remove the embedded object and recursively any 
    #other embedded embedded object.
    simpleEmbeddingSemantics = True
    
    def __init__(self, requestProcessor, model_factory=None,
                 schemaFactory=defaultSchemaClass,
                 storage_path ='',
                 storage_template='',
                 storage_template_path='',
                 application_model='',
                 transaction_log = '',
                 save_history = False,
                 version_storage_path='',
                 version_model_factory=None,
                 storage_template_options=None,
                 model_options=None,
                 changeset_hook=None,
                 trunk_id = '0A', 
                 branch_id = None,                  
                 **kw):
        '''
        model_factory is a base.Model class or factory function that takes
        two parameters:
          a location (usually a local file path) and iterator of Statements
          to initialize the model if it needs to be created
        '''
        self.requestProcessor = requestProcessor
        self.model_factory = model_factory
        self.version_model_factory = version_model_factory
        self.schemaFactory = schemaFactory 
        self.application_model = application_model        
        self.storage_path = storage_path        
        self.version_storage_path = version_storage_path
        self.storage_template = storage_template
        self.storage_template_path = storage_template_path
        self.transaction_log = transaction_log
        self.save_history = save_history
        self.storage_template_options = storage_template_options or {}
        self.trunk_id = trunk_id
        self.branch_id = branch_id
        self.changesetHook = changeset_hook
        self._txnparticipants = []
        self.model_options = model_options or {}

    def load(self):
        requestProcessor = self.requestProcessor
        self.log = logging.getLogger("datastore." + requestProcessor.app_name)

        #normalizeSource = getattr(self.model_factory, 'normalizeSource',
        #                                        DataStore._normalizeSource)
        #source is the data source for the store, usually a file path
        #source = normalizeSource(self, requestProcessor, self.storage_path)
        source = self.storage_path
        if not self.storage_template and self.storage_template_path:
            self.storage_template = open(self.storage_template_path).read()
        model, defaultStmts, historyModel, lastScope = self.setupHistory(source)
        if not model:
            #setupHistory didn't initialize the store, so do it now
            #model_factory will load the store specified by `source` or create
            #new one at that location and initializing it with `defaultStmts`            
            model_factory = self.model_factory
            if not model_factory:
                if source:
                    model_factory = FileStore
                else:
                    model_factory = MemStore
            self.log.info("Using %s at '%s'" % (model_factory.__name__, source))
            model = model_factory(source=source, defaultStatements=defaultStmts,
                                                            **self.model_options)
                
        #if there's application data (data tied to the current revision
        #of your app's implementation) include that in the model
        if self.application_model:
            stmtGen = base.parseRDFFromString(self.application_model, 
                requestProcessor.model_uri, scope=graphmod.APPCTX) 
            appmodel = MemStore(stmtGen)
            #XXX MultiModel is not very scalable -- better would be to store 
            #the application data in the model and update it if its difference 
            #from what's stored (this requires a context-aware store)
            model = base.MultiModel(model, appmodel)
        
        if self.save_history:
            model, historyModel = self._addModelTxnParticipants(model, historyModel)
            self.model = self.graphManager = graphmod.MergeableGraphManager(model, 
                historyModel, requestProcessor.model_uri, lastScope, self.trunk_id, self.branch_id) 
            if self._txnparticipants:
                self._txnparticipants.insert(0, #must go first
                        TwoPhaseTxnGraphManagerAdapter(self.graphManager))
        else:
            self.model = self._addModelTxnParticipants(model)[0]
            self.graphManager = None

        #turn on update logging if a log file is specified, which can be used to 
        #re-create the change history of the store
        if self.transaction_log:
            if not isinstance(self.transaction_log, (str,unicode)):
                if (self.storage_path
                    and isinstance(self.storage_path, (str,unicode))):
                    self.transaction_log = self.storage_path + '.log.nt'
                elif self.storage_template_path:
                    self.transaction_log = self.storage_template_path + '.log.nt'
                else:
                    self.log.warning("unable to determine path for transaction_log")
            if isinstance(self.transaction_log, (str,unicode)):
                #XXX doesn't log history model if store is split
                #XXX doesn't log models that are TransactionParticipants themselves
                #XXX doesn't log models that don't support updateAdvisory
                if isinstance(self.model, ModelWrapper):
                    self.model.adapter.logPath = self.transaction_log
                else:
                    self.log.warning(
                "transaction_log is configured but not compatible with model")
        
        if self.changesetHook:
            assert self.save_history, "replication requires save_history to be on"
            self.model.notifyChangeset = self.changesetHook
        
        #set the schema (default is no-op)
        self.schema = self.schemaFactory(self.model)
        #XXX need for graphManager?:
        #self.schema.setEntailmentTriggers(self._entailmentAdd, self._entailmentRemove)
        if isinstance(self.schema, base.Model):
            self.model = self.schema

        #hack!:
        if self.model_options.get('parseOptions', self.storage_template_options
                                           ).get('generateBnode') == 'counter':
            model.bnodePrefix = '_:'
            self.model.bnodePrefix = '_:'

    def setupHistory(self, source):
        requestProcessor = self.requestProcessor

        #data used to initialize a new store
        defaultStmts = base.parseRDFFromString(self.storage_template, 
                        requestProcessor.model_uri,
                        options=self.storage_template_options) 
        
        if self.save_history == 'split':                                                
            version_model_factory = self.version_model_factory
            versionModelOptions = {}
            if not version_model_factory:
                if self.version_storage_path and self.model_factory:                    
                    #if a both a version path and the model_factory was set, use the model factory
                    version_model_factory = self.model_factory
                    versionModelOptions = self.model_options
                elif self.storage_path or self.version_storage_path: #use the default
                    version_model_factory = IncrementalNTriplesFileStoreBase
                else:
                    version_model_factory = MemStore
            
            if not self.version_storage_path and issubclass(version_model_factory, FileStore):
                #generate path based on primary path
                assert self.storage_path
                import os.path
                versionStoreSource = os.path.splitext(self.storage_path)[0] + '-history.nt'
            else:
                versionStoreSource = self.version_storage_path
            
            if versionStoreSource:
                normalizeSource = getattr(self.version_model_factory, 
                        'normalizeSource', DataStore._normalizeSource)
                versionStoreSource = normalizeSource(self, requestProcessor,
                                                     versionStoreSource)
            revisionModel = version_model_factory(source=versionStoreSource,
                                        defaultStatements=[], **versionModelOptions)
        else:
            #either no history or no separate model
            revisionModel = None
        
        model = None
        lastScope = None        
        return model, defaultStmts, revisionModel, lastScope

    def isDirty(self, txnService):
        '''return True if this transaction participant was modified'''    
        return txnService.state.additions or txnService.state.removals
    
    def is2PhaseTxn(self):
        return not not self._txnparticipants

    def commitTransaction(self, txnService):
        if self.is2PhaseTxn():
            return
        self.model.commit(**txnService.getInfo())

    def abortTransaction(self, txnService):
        if self.is2PhaseTxn():
            return 
        
        if not self.isDirty(txnService):
            if self.graphManager:
               self.graphManager.rollback() 
            return
        self.model.rollback()

    def getTransactionContext(self):
        if self.graphManager:
            return self.graphManager.getTxnContext() #return a contextUri
        return None
    
    def join(self, txnService, readOnly=False, setCurrentTxn=True):
        if not txnService.isActive():
            return False
        
        super(BasicStore,self).join(txnService, readOnly)
        
        if not hasattr(txnService.state, 'queryCache'):
            #create a cache that will be used by the query engine
            #its local to this transaction so dont have worry about memory usage
            #or invalidating across transactions or processes
            txnService.state.queryCache = {}

        #getTransactionContext() can invoke store IO so for efficent don't do if readOnly
        if not readOnly and setCurrentTxn and hasattr(txnService.state, 'kw'):
            txnCtxtResult = self.getTransactionContext()
            txnService.state.kw['__current-transaction'] = txnCtxtResult
                
        for participant in self._txnparticipants:
            participant.join(txnService, readOnly)
        return True

    def _addModelTxnParticipants(self, model, historyModel=None):
        if historyModel:
            txnOk = model.updateAdvisory or isinstance(model, 
                                           transactions.TransactionParticipant)
            if txnOk:
                txnOk = historyModel.updateAdvisory or isinstance(historyModel,
                                           transactions.TransactionParticipant)
        else:
            txnOk = model.updateAdvisory or isinstance(model, 
                                           transactions.TransactionParticipant)
        
        if txnOk:
            def add(model):
                if not model:
                    return model
                if not isinstance(model, transactions.TransactionParticipant):
                    participant = TwoPhaseTxnModelAdapter(model)
                    model = ModelWrapper(model, participant)
                else:
                    participant = model
                self._txnparticipants.append(participant)
                return model
            
            return [add(m) for m in model, historyModel]
        else:
            self.log.warning(
"model(s) doesn't support updateAdvisory, unable to participate in 2phase commit")
            return model, historyModel
    
    def _isEmbedded(self, res, objectType = base.OBJECT_TYPE_RESOURCE):
        return (self.simpleEmbeddingSemantics 
                and res.startswith(self.model.bnodePrefix+'j:e:') 
                and objectType == base.OBJECT_TYPE_RESOURCE)

    def _getPropListName(self, resource, prop):
        return self.model.bnodePrefix+'j:proplist:'+ resource+';'+prop
    
    def _toStatements(self, json):
        #if we parse pjson, make sure we generate the same kind of bnodes as the model
        parseOptions=self.model_options.get('parseOptions', 
                                    self.storage_template_options)
        #XXX add parseOptions parameter that can overrides config settings
        return _toStatements(json, **parseOptions)
        
    def add(self, adds):
        return self._add(adds, False)[0]
        
    def _add(self, adds, mustBeNewResources):
        '''
        Adds data to the store.

        `adds`: A list of either statements or pjson conforming dicts
        '''
        if not self.join(self.requestProcessor.txnSvc):
            #not in a transaction, so call this inside one
            func = lambda: self._add(adds, mustBeNewResources)
            return self.requestProcessor.executeTransaction(func)
        
        stmts, jsonrep, emptyobjs = self._toStatements(adds)
        resources = set()
        newresources = []
        if stmts: #invalidate cache
            self.requestProcessor.txnSvc.state.queryCache = {}
        for s in stmts:
            if mustBeNewResources or self.newResourceTrigger:
                subject = s[0]
                if subject not in resources:
                    resources.update(subject)
                    if not self.model.getStatements(subject, hints=dict(limit=1)):
                        newresources.append(subject)
                    elif mustBeNewResources:
                        raise DataStoreError("id %s already exists" % subject)
        
        if self.newResourceTrigger and newresources:  
            self.newResourceTrigger(newresources)
        if self.addTrigger and stmts:
            self.addTrigger(stmts, jsonrep)
        self.model.addStatements(stmts)
        return jsonrep or stmts, newresources

    def create(self, adds):
        '''
        Adds data to the store. If the id of any resource is already present 
        in the datastore an exception is raised.

        `adds`: A list of either statements or pjson conforming dicts        
        '''
        return self._add(adds, True)

    def _removePropLists(self, stmts):
        if not self.model.canHandleStatementWithOrder:
            for stmt in stmts:
                #check if the statement is part of a json list, remove that list item too                
                rows = list(pjson.findPropList(self.model, stmt[0], stmt[1], stmt[2], stmt[3], stmt[4]))
                for row in rows:
                    self.model.removeStatement(base.Statement(*row[:5]))

    def _getStatementsForResources(self, resources):
        stmts = []
        for r in resources:
            currentStmts = self.model.getStatements(r)
            for s in currentStmts:
                #it's an RDF list, we need to follow all the nodes and remove them too
                if s.predicate == base.RDF_SCHEMA_BASE+u'next':                    
                    while s:                        
                        listNodeStmts = self.model.getStatements(s.object)
                        stmts.extend(listNodeStmts)
                        s = flatten([ls for ls in listNodeStmts 
                                    if ls.predicate == base.RDF_SCHEMA_BASE+u'next'])
                        assert not isinstance(s, list)
            stmts.extend(currentStmts)
        return stmts

    def _removeEmbedded(self, removals, skipSet):
        '''
        remove anonymous embedded objects
        '''
        #this assumes that an embedded object is referenced by one and only one
        #property rooted in the object that the embedded object names
        embeddedRemovals = set()
        for stmt in removals:
            if self._isEmbedded(stmt.object, stmt.objectType):
                if stmt.object not in skipSet:
                    embeddedRemovals.add(stmt.object)
        moreRemovals = self._getStatementsForResources(embeddedRemovals)
        if moreRemovals:
            #recursively follow looking for new embedded objects
            skipSet.update(embeddedRemovals)
            return removals + self._removeEmbedded(moreRemovals, skipSet)
        else:
            return removals
        
    def remove(self, removes):
        '''
        Removes data from the store.
        
        `removes`: A list of a statements or list containing pjson-conforming dicts and strings.
        
        If the item is a string it will be treated as an object reference and
        the entire resource will be removed. 
        If the object is a dict, the specified property/value pairs will be removed from the store,
        unless the value is null. In that case, the property and all associated values
        will be deleted.
        '''
        if not self.join(self.requestProcessor.txnSvc):
            #not in a transaction, so call this inside one
            func = lambda: self.remove(removes)
            return self.requestProcessor.executeTransaction(func)

        resources = []        
        if isinstance(removes, list):
            objs = []
            parseOptions=self.model_options.get('parseOptions', 
                                        self.storage_template_options)
            p = pjson.Parser(**parseOptions)
            for r in removes:
                if isinstance(r, (str,unicode)):
                    resources.append( p.defaultParseContext.parseId(r) )
                else:
                    objs.append(r)
            removes = objs
        
        stmts, jsonrep, emptyobjs = self._toStatements(removes)
        if jsonrep is None:
            #must have just been statements, not pjson
            assert not resources
            return self._remove(stmts)

        #for each resource, property where value is null, remove all values
        for s in [s for s in stmts if s[3] == pjson.JSON_BASE+'null']:
            stmts.remove(s)
            self._removePropLists([(s[0], s[1], None, None, None)])
            currentStmts = self.model.getStatements(s[0], s[1], context = s[4] or None)
            stmts.extend(currentStmts)
                
        for res in resources:
            stmts.extend( self._getStatementsForResources(resources) )
        
        stmts.extend( self._removeEmbedded(stmts, set()) )
        return self._remove(stmts)
        
    def _remove(self, removes):
        stmts, jsonrep, emptyobjs = self._toStatements(removes)
        if stmts: #invalidate cache
            self.requestProcessor.txnSvc.state.queryCache = {}

        if self.removeTrigger and stmts:
            self.removeTrigger(stmts, jsonrep)        
        self._removePropLists(stmts)
        self.model.removeStatements(stmts)
        
        return jsonrep or stmts

    def update(self, updates):
        '''
        Update the store by either adding or replacing the property value pairs
        given in the update, depending on whether or not the pair currently 
        appears in the store.

        See also `replace`.

        `updates`: A list of either statements or pjson conforming dicts
        '''
        return self.updateAll(updates, [])

    def replace(self, replacements):
        '''
        Replace the given objects in the store. Unlike `update` this method will
        remove properties in the store that aren't specified.
        Also, if the data contains json object and an object has no properties
        (just an `id` property), the object will be removed.

        See also `update` and `updateAll`.

        `replacements`: A list of either statements or pjson conforming dicts
        '''
        return self.updateAll([], replacements)

    def updateAll(self, update, replace, removedResources=None):
        '''
        Add, remove, update, or replace resources in the store.

        `update`: A list of either statements or pjson conforming dicts that will
        be processed with the same semantics as the `update` method.
        
        `replace`: A list of either statements or pjson conforming dicts that will
        be processed with the same semantics as the `replace` method.
        
        `removedResources`: A list of ids of resources that will be removed 
        from the store.
        '''
        if not self.join(self.requestProcessor.txnSvc):
            #not in a transaction, so call this inside one
            func = lambda: self.updateAll(update, replace, removedResources)
            return self.requestProcessor.executeTransaction(func)
        
        newStatements = []
        newListResources = set()
        removedResources = set(removedResources or [])
        removals = []
        skipListValues = []
        
        #update:
        #replace stmts with matching subject and property
        #if the old value is a list, remove the entire list
        #XXX handle scope: if a non-empty scope is specified, only compare        
        updateStmts, ujsonrep, emptyobjs = self._toStatements(update)
        root = OrderedModel(updateStmts, self._isEmbedded)
        currentListResource = None
        for (resource, prop, values) in root.groupbyProp():
            #note: for list resources, rdf:type will be sorted first 
            #but don't assume they are present
            if currentListResource == resource:
                continue
            if (prop == base.RDF_MS_BASE+'type' and 
                (pjson.PROPSEQTYPE, base.OBJECT_TYPE_RESOURCE) in values):
                currentListResource = resource
                newListResources.add(resource)
                continue
            if prop in (base.RDF_SCHEMA_BASE+u'member', 
                                base.RDF_SCHEMA_BASE+u'first'):
                #if list just replace the entire list
                removedResources.add(resource)
                currentListResource = resource
                newListResources.add(resource)
                continue
            
            currentStmts = self.model.getStatements(resource, prop)
            if currentStmts:
                currentValues = [(s.object, s.objectType) for s in currentStmts]
                for currentStmt in currentStmts:
                    currentObject, currentObjectType = currentStmt[2:4]
                    found = None
                    if (currentObject, currentObjectType) in values:
                        found = currentObject, currentObjectType
                    else:
                        if (self._isEmbedded(currentObject,currentObjectType)
                            and currentObject not in root.subjectDict):
                            #instead of replacing stmts, rename new embedded 
                            #resource to old name (but only if new name doesn't
                            #match another existing name and old name isn't used)
                            embeddedvalues = [v[0] for v in values if 
                                self._isEmbedded(*v) and v not in currentValues]
                            if embeddedvalues:                                
                                #not optimal, but for now just take the first one                                            
                                embeddedvalue = embeddedvalues.pop(0)
                                found = embeddedvalue, currentObjectType
                                #give the new bnode the same name as the old one
                                #note: bnode subjects are sorted last so modifying
                                #those statement now is ok
                                root.renameResource(embeddedvalue, currentObject)
                    if found:
                        values.remove(found)
                        listuri = self._getPropListName(resource, prop)
                        skipListValues.append( (listuri, found) )
                    else:    
                        #new statement replaces current statement
                        removals.append(currentStmt)
                        self._removePropLists( (currentStmt,) )                        
            for value, valueType in values:                
                newStatements.append( base.Statement(resource,prop, value, valueType) )
         
        for listRes in newListResources:
            for liststmt in root.subjectDict[listRes]:
                if (liststmt[0], liststmt[2:4]) not in skipListValues:
                    newStatements.append( liststmt )
        
        #replace:
        #replace all properties of the given resources
        replaceStmts, replaceJson, emptyobjs = self._toStatements(replace)
        if emptyobjs:
            removedResources.update(emptyobjs)
        
        #get all statements with the subject and remove them (along with associated lists)        
        root = OrderedModel(replaceStmts, self._isEmbedded)
        renamed = {}
        for resource in root.resources:
            currentStmts = self.model.getStatements(resource)
            newStmts = root.getProperties(resource)
            currentEmbedded = None
            for stmt in currentStmts:
                matchStmt = None                
                if stmt not in newStmts:
                    if (self._isEmbedded(stmt.object,stmt.objectType)
                                and stmt.object not in root.subjectDict):
                        #see if we can just rename an new embedded object 
                        #instead of replacing this stmt
                        for newstmt in newStmts:
                            if newstmt[1] == stmt[1] and self._isEmbedded(newstmt[2],newstmt[3]):
                                if currentEmbedded is None:
                                    currentEmbedded = [s.object for s in currentStmts 
                                           if self._isEmbedded(s.object, s.objectType)]
                                #only replace if the new name isn't an existing name
                                if newstmt.object not in currentEmbedded and newstmt.object not in renamed:
                                    matchStmt = newstmt
                                    listuri = self._getPropListName(newstmt[0], newstmt[1])
                                    root.renameResource(newstmt.object, stmt.object, listuri)
                                    renamed[newstmt.object] = stmt.object
                                    newStmts = root.getProperties(resource)
                                    break
                else:
                    matchStmt = stmt
                
                if matchStmt:                
                    root.removeStatement(matchStmt)
                else:
                    removals.append(stmt)
            #the new proplist probably have different ids even for values that
            #don't need to be added so remove all current proplists
            self._removePropLists(currentStmts)
        newStatements.extend( root.getAll() )
        
        #remove: remove all statements and associated lists
        removals.extend( self._getStatementsForResources(removedResources) )
        
        embeddedAdded = set()
        for stmt in newStatements:
            if self._isEmbedded(stmt.object, stmt.objectType):
                embeddedAdded.add(stmt.object)            
        removals.extend(self._removeEmbedded(removals, embeddedAdded))
        
        self._remove(removals)
        addStmts = self.add(newStatements)

        return addStmts, removals

    def query(self, query=None, bindvars=None, explain=None, debug=False, 
        forUpdate=False, captureErrors=False, contextShapes=None, useSerializer=True):
        import vesper.query
        #XXX theorectically some queries might not be readonly, set flag as appropriate
        if not self.join(self.requestProcessor.txnSvc, readOnly=True):
            #not in a transaction, so call this inside one
            func = lambda: self.query(query, bindvars, explain,
                        debug, forUpdate, captureErrors, contextShapes, useSerializer)
            return self.requestProcessor.executeTransaction(func)
        
        if not contextShapes:
            contextShapes = {dict:defaultattrdict}
        if useSerializer and isinstance(useSerializer, (bool, int, float)):            
            pjsonOptions=self.model_options.get('serializeOptions',{}).get('pjson')
            if pjsonOptions is not None:
                useSerializer = pjsonOptions
        
        start = time.clock()
        cache = self.requestProcessor.txnSvc.state.queryCache
        results = vesper.query.getResults(query, self.model, bindvars, explain,
          debug, forUpdate, captureErrors, contextShapes, useSerializer, cache)
        elapsed = time.clock() - start
        self.log.debug('%s elapsed for query %s', elapsed, query)
        if not captureErrors and not explain and not debug:
            return results.results
        else:
            return results

    def merge(self,changeset): 
        if not self.join(self.requestProcessor.txnSvc, setCurrentTxn=False):
            #not in a transaction, so call this inside one
            func = lambda: self.merge(changeset)
            return self.requestProcessor.executeTransaction(func) 
        
        assert isinstance(self.graphManager, graphmod.MergeableGraphManager)
        assert isinstance(self._txnparticipants[0], TwoPhaseTxnGraphManagerAdapter)
        graphTxnManager = self._txnparticipants[0]
        try:
            #TwoPhaseTxnGraphManagerAdapter.isDirty() might be wrong when merging
            graphTxnManager.dirty = self.graphManager.merge(changeset)
            return graphTxnManager.dirty
        except:
            graphTxnManager.dirty = True
            raise

class TwoPhaseTxnModelAdapter(transactions.TransactionParticipant):
    '''
    Adapts models which doesn't support transactions or only support simple (one-phase) transactions.
    '''
    logPath = None
    
    def __init__(self, model):
        self.model = model
        self.committed = False
        self.undo = []
        assert model.updateAdvisory, 'need this for undo to work accurately'
    
    def isDirty(self,txnService):
        '''return True if this transaction participant was modified'''
        return txnService.state.additions or txnService.state.removals    
    
    def voteForCommit(self, txnService):
        #the only way we can tell if commit will succeed is to do it now 
        #if not self.model.autocommit:
        self.model.commit(**txnService.getInfo())
        #else: already committed
        self.committed = True
                                        
    def commitTransaction(self, txnService):
        #already commited, nothing to do
        assert self.committed
        if self.logPath:
            self.logChanges(txnService)
        self.undo = []
        self.committed = False
    
    def abortTransaction(self, txnService):
        if not self.committed and not self.model.autocommit:
            self.model.rollback()
        else:
            #already committed, commit a compensatory transaction
            #if we're in recovery mode make sure the change isn't already in the store
            if self.undo:
                try:
                    for stmt in self.undo:
                        if stmt[0] is base.Removed:
                            #if not recover or self.model.getStatements(*stmt[1]):
                            self.model.addStatement( stmt[1] )
                        else:
                            self.model.removeStatement( stmt[0] )
                    #if not self.model.autocommit:
                    self.model.commit()
                except:
                    #import traceback; traceback.print_exc()
                    pass
        self.undo = []
        self.committed = False

    def logChanges(self, txnService):
        import time
        outputfile = file(self.logPath, "a+")
        changelist = self.undo
        def unmapQueue():
            for stmt in changelist:
                if stmt[0] is base.Removed:
                    yield base.Removed, stmt[1]
                else:
                    yield stmt[0]
                    
        comment = txnService.getInfo().get('source','') or ''
        if isinstance(comment, (list, tuple)):
            comment = comment and comment[0] or ''
            
        outputfile.write("#begin " + comment + "\n")            
        base.writeTriples( unmapQueue(), outputfile)            
        outputfile.write("#end " + time.asctime() + ' ' + comment + "\n")
        outputfile.close()

class TwoPhaseTxnGraphManagerAdapter(transactions.TransactionParticipant):
    '''
    Each underlying model is a wrapped with a TwoPhaseTxnModelAdapter if necessary.
    This must be be listed before those participants
    '''
    
    ctxStmts = None
    
    def __init__(self, graph):
        assert isinstance(graph, graphmod.NamedGraphManager)
        self.graph = graph
        self.dirty = False

    def isDirty(self,txnService):
        '''return True if this transaction participant was modified'''
        return self.dirty or txnService.state.additions or txnService.state.removals    

    def readyToVote(self, txnService):
        #need to do this now so the underlying model gets ctxStmts before it commits
        if self.graph._currentTxn: #simple merging doesn't create a graph txn 
            self.ctxStmts = self.graph._finishCtxResource(txnService.getInfo())
        return True
    
    #no-op -- txnparticipants for underlying models will commit     
    #def voteForCommit(self, txnService): pass
    
    def commitTransaction(self, txnService):
        if self.ctxStmts:
            self.graph._finalizeCommit(self.ctxStmts)
        self.graph._currentTxn = None
        self.ctxStmts = None
        self.dirty = False

    def abortTransaction(self, txnService):
        if self.ctxStmts:
            #undo the transaction we just voted for
            graph = self.graph
            assert not graph._currentTxn, 'shouldnt be inside a transaction'
           
            #set the current revision to one prior to this
            baseRevisions = [s.object for s in ctxStmts if s[1] == graphmod.CTX_NS+'baseRevision']
            assert len(baseRevisions) == 1
            baseRevision = baseRevisions[0]
            #note: call _markLatest makes db changes so this abort needs to be 
            #called before underlying models' abort
            graph._markLatest(baseRevision)
            graph.currentVersion = baseRevision
        self.graph._currentTxn = None
        self.ctxStmts = None
        self.dirty = False

class ModelWrapper(base.Model):

    def __init__(self, model, adapter):
        self.model = model
        self.adapter = adapter
        
    def __getattribute__(self, name):
        #we can't use __getattr__ because we don't want base class attributes
        #returned, we want those to be delegated
        if name in ModelWrapper.__dict__ or name in ('model', 'adapter'):
            return object.__getattribute__(self, name)
        else:
            assert name not in ('addStatement', 'removeStatement', 'addStatements')
            return getattr(object.__getattribute__(self, 'model'), name)

    def addStatement(self, statement):
        '''add the specified statement to the model'''
        added = self.model.addStatement(statement)
        if added:
            self.adapter.undo.append((statement,))
        return added

    def removeStatement(self, statement):
        '''removes the statement'''
        removed = self.model.removeStatement(statement)
        if removed:
            self.adapter.undo.append((base.Removed, statement))
        return removed
        
    #disable optimized paths
    def addStatements(self, stmts):
        return base.Model.addStatements(self, stmts)

    def removeStatements(self, stmts):
        return base.Model.removeStatements(self, stmts)
