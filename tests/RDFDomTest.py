"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest, os, os.path, glob, tempfile
import cStringIO
from pprint import *
   
from rx.RxPath import *
def RDFDoc(model, nsMap):
    from rx import RxPathGraph
    graphManager = RxPathGraph.NamedGraphManager(model, None,None)
    graphManager.createCtxResource = False
    return createDOM(model, nsMap, graphManager=graphManager)

import difflib, time
from rx.RxPathUtils import _parseTriples as parseTriples
    
class RDFDomTestCase(unittest.TestCase):
    ''' tests rdfdom, rxpath, rxslt, and xupdate on a rdfdom
        tests models with:
            bNodes
            literals: empty (done for xupdate), xml, text with invalid xml characters, binary
            advanced rdf: rdf:list, containers, datatypes, xml:lang
            circularity 
            empty element names (_)
            multiple rdf:type
            RDF Schema support
        diffing and merging models
    '''

    model1 = r'''#test
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790527.921" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790527.921" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#summary> "l" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#content-length> "13" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#hasContent> "            kkk &nbsp;" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "XPmK/UXVwPzgKryx1EwoHtTMe34=" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#name> "test" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790874.703" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790874.703" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#summary> "lll" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "jERppQrIlaay2cQJsz36xVNyQUs=" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#hasContent> "        kkkk    &nbsp;" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#content-length> "20" .
'''

    model2 = r'''<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "ndKxl8RGTmr3uomnJxVdGnWgXuA=" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#hasContent> " llll"@en-US .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#content-length> "5"^^http://www.w3.org/2001/XMLSchema#int .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#created-on> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#summary> "ppp" .'''

    loopModel = r'''<http://loop.com#r1> <http://loop.com#prop> <http://loop.com#r1>.
<http://loop.com#r2> <http://loop.com#prop> <http://loop.com#r3>.
<http://loop.com#r3> <http://loop.com#prop> <http://loop.com#r2>.'''
    
    model1NsMap = { 'rdf' : RDF_MS_BASE, 
                    'rdfs' : RDF_SCHEMA_BASE,
                    'bnode' : "bnode:",
                    'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
                    'a' : "http://rx4rdf.sf.net/ns/archive#" }

    def setUp(self):        
        if DRIVER == '4Suite':
            self.loadModel = self.loadFtModel
        elif DRIVER == 'RDFLib':
            self.loadModel = self.loadRdflibModel
        elif DRIVER == 'Redland':
            self.loadModel = self.loadRedlandModel
        elif DRIVER == 'Mem':
            self.loadModel = self.loadMemModel
        else:
            raise "unrecognized driver: " + DRIVER
        #from rx import RxPath
        #RxPath.useQueryEngine = True

    def loadFtModel(self, source, type='nt'):
        if type == 'rdf':
            #assume relative file
            model, self.db = Util.DeserializeFromUri('file:'+source, scope='')
        else:
            model, self.db = DeserializeFromN3File( source )
        #use TransactionFtModel because we're using 4Suite's Memory
        #driver, which doesn't support transactions
        return TransactionFtModel(model)

    def loadRedlandModel(self, source, type='nt'):
        #ugh can't figure out how to close an open store!
        #if hasattr(self,'rdfDom'):
        #    del self.rdfDom.model.model._storage
        #    import gc; gc.collect()             

        if type == 'rdf':
            assert False, 'Not Supported'
        else:            
            for f in glob.glob('RDFDomTest*.db'):
                if os.path.exists(f):
                    os.unlink(f)
            if isinstance(source, (str, unicode)):
                stream = file(source, 'r+')
            else:
                stream = source
            stmts = NTriples2Statements(stream)
            return RedlandHashMemModel("RDFDomTest", stmts)
            #return RedlandHashBdbModel("RDFDomTest", stmts)

    def loadRdflibModel(self, source, type='nt'):
        dest = tempfile.mktemp()
        if type == 'rdf':
            type = 'xml'
        return initRDFLibModel(dest, source, type)

    def loadMemModel(self, source, type='nt'):
        if type == 'nt':
            type = 'ntriples'
        elif type == 'rdf':
            type = 'rdfxml'        
        if isinstance(source, (str, unicode)):
            return TransactionMemModel(parseRDFFromURI('file:'+source,type))
        else:
            return TransactionMemModel(parseRDFFromString(source.read(),'test:', type))
        
    def getModel(self, source, type='nt'):
        model = self.loadModel(source, type)
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        return RDFDoc(model, self.nsMap)
       
    def tearDown(self):
        pass

    def testNtriples(self):
        #we don't include scope as part of the Statements key
        st1 = Statement('test:s', 'test:p', 'test:o', 'R', 'test:c')
        st2 = Statement('test:s', 'test:p', 'test:o', 'R', '')
        self.failUnless(st2 in [st1] and [st2].index(st1) == 0)
        self.failUnless(st1 in {st2:1}  )
        
        #test character escaping 
        s1 = r'''bug: File "g:\_dev\rx4rdf\rx\Server.py", '''
        n1 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "bug: File \"g:\\_dev\\rx4rdf\\rx\\Server.py\", ".'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n1])]
        self.failUnless(s1 == object)
        #test xml:lang support
        n2 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "english"@en-US.'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n2])]
        self.failUnless(object=="english" and objectType == 'en-US')
        #test datatype support
        n3 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents>'''\
        ''' "1"^^http://www.w3.org/2001/XMLSchema#int.'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n3])]
        self.failUnless(object=="1" and objectType == 'http://www.w3.org/2001/XMLSchema#int')

        sio = cStringIO.StringIO()
        writeTriples( [Statement('test:s', 'test:p', u'\x10\x0a\\\u56be',
                                 OBJECT_TYPE_LITERAL)], sio, 'ascii')
        self.failUnless(sio.getvalue() == r'<test:s> <test:p> "\u0010\n\\\u56BE" .'
                        '\n')                      

        #test URI validation when writing triples
        out = cStringIO.StringIO()
        self.failUnlessRaises(RuntimeError, lambda:
            writeTriples( [Statement(BNODE_BASE+'foo bar', 'http://foo bar', 
                'http://foo bar')], out) )
        writeTriples( [Statement(BNODE_BASE+'foobar', 'http://foo', 
                'http://foo bar')], out)         
        self.failUnlessRaises(RuntimeError, lambda:
            writeTriples( [Statement(BNODE_BASE+'foobar', 'http://foo', 
                'http://foo bar',OBJECT_TYPE_RESOURCE)], out) )

    def testSerializeJson(self):
        model = r'''<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "ndKxl8RGTmr3u/omnJxVdGnWgXuA=" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#hasContent> " llll"@en-US .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#content-length> "5"^^http://www.w3.org/2001/XMLSchema#int .
_:1 <http://rx4rdf.sf.net/ns/wiki#name> _:1 .
_:1 <http://rx4rdf.sf.net/ns/wiki#name> _:2 .
'''
        model = self.loadModel(cStringIO.StringIO(model), 'nt')
        stmts = model.getStatements()
        json = serializeRDF(stmts, 'json')
        newstmts = parseRDFFromString(json,'', 'json')
        stmts.sort()
        newstmts.sort()
        #print stmts
        #print newstmts
        self.failUnless(stmts == newstmts)
        
    def testDiff(self):
        self.rdfDom = self.getModel("about.rx.nt")
        updateDom = self.getModel("about.diff1.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #nothing should have changed
        self.failUnless( not added and not removed and not reordered )

        updateDom = self.getModel("about.diff2.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #we've added one non-list statement and changed the first list item (and so 1 add, 1 remove)
        self.failUnless( len(added) == len(reordered) ==
            len(reordered.values()[0][0]) == len(reordered.values()[0][1]) == 1 
            and not len(removed))

        updateDom = self.getModel("about.diff3.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #with this one we've just re-ordered the list, so no statements should be listed as added or removed
        self.failUnless(reordered and len(reordered.values()[0][0]) == len(reordered.values()[0][1]) == 0)
        
    def _mergeAndUpdate(self, updateDom, resources):
        statements, nodesToRemove = mergeDOM(self.rdfDom, updateDom ,resources)
        #print 'res'; pprint( (statements, nodesToRemove) )
        
        #delete the statements or whole resources from the dom:            
        for node in nodesToRemove:
            node.parentNode.removeChild(node)
        #and add the statements
        addStatements(self.rdfDom, statements)
        return statements, nodesToRemove

    def testStatement(self):
        self.failUnless(Statement('s', 'o', 'p') == Statement('s', 'o', 'p'))
        self.failUnless(Statement('s', 'o', 'p','L') == Statement('s', 'o', 'p'))        
        self.failUnless(Statement('s', 'o', 'p',scope='C1') == Statement('s', 'o', 'p', scope='C2'))
        self.failUnless(Statement('s', 'o', 'p','L','C') == Statement('s', 'o', 'p'))
        self.failUnless(not Statement('s', 'o', 'p','L','C') != Statement('s', 'o', 'p'))
        self.failUnless(Statement('s', 'p', 'a') < Statement('s', 'p', 'b'))
    
    def testMerge(self):        
        self.rdfDom = self.getModel("about.rx.nt")
        updateDom = self.getModel("about.diff1.nt")
            
        statements, nodesToRemove = mergeDOM(self.rdfDom, updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])                
        #nothing should have changed
        #pprint((statements, nodesToRemove))
        self.failUnless( not statements and not nodesToRemove )

        self.rdfDom = self.getModel("about.rx.nt")
        updateDom = self.getModel("about.diff2.nt")
        def nr(node): print 'new', node.uri
        updateDom.newResourceTrigger = nr

        #we've added and removed one non-list statement and changed the first list item
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( statements and nodesToRemove )
        #merge in the same updateDom in again, this time there should be no changes
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])

        self.failUnless( not statements and not nodesToRemove )

        self.rdfDom = self.getModel("about.rx.nt")        
        updateDom = self.getModel("about.diff3.nt")
        #with this one we've just re-ordered the list,
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( statements and nodesToRemove )
        #merge in the same updateDom in again, this time there should be no changes
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( not statements and not nodesToRemove )
                        
DRIVER = 'Mem'

if DRIVER == '4Suite':
    from Ft.Rdf import Util
    from Ft.Rdf.Statement import Statement as FtStatement
    from Ft.Rdf.Model import Model as Model4Suite
    #this function is no longer used by RxPath
    def DeserializeFromN3File(n3filepath, driver=Memory, dbName='', create=0, defaultScope='',
                            modelName='default', model=None):
        if not model:
            if create:
                db = driver.CreateDb(dbName, modelName)
            else:
                db = driver.GetDb(dbName, modelName)
            db.begin()
            model = Model4Suite(db)
        else:
            db = model._driver
            
        if isinstance(n3filepath, ( type(''), type(u'') )):
            stream = file(n3filepath, 'r+')
        else:
            stream = n3filepath
            
        #bNodeMap = {}
        #makebNode = lambda bNode: bNodeMap.setdefault(bNode, generateBnode(bNode))
        makebNode = lambda bNode: BNODE_BASE + bNode
        for stmt in parseTriples(stream,  makebNode):
            if stmt[0] is Removed:            
                stmt = stmt[1]
                scope = stmt[4] or defaultScope
                model.remove( FtStatement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )
            else:
                scope = stmt[4] or defaultScope
                model.add( FtStatement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )                
        #db.commit()
        return model, db


def profilerRun(testname, testfunc):
    import hotshot, hotshot.stats
    global prof
    prof = hotshot.Profile(testname+".prof")
    try:
        testfunc() #prof.runcall(testfunc)
    except:
        import traceback; traceback.print_exc()
    prof.close()

    stats = hotshot.stats.load(testname+".prof")
    stats.strip_dirs()
    stats.sort_stats('cumulative','time')
    #stats.sort_stats('time','calls')
    stats.print_stats(100)            

if __name__ == '__main__':
    import sys
    from rx import logging
    logging.root.setLevel(logging.DEBUG)
    logging.basicConfig()

    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))    
    if sys.argv.count('--driver'):
        arg = sys.argv.index('--driver')
        DRIVER = sys.argv[arg+1]
        del sys.argv[arg:arg+2]

    profile = sys.argv.count('--prof')
    if profile:
        del sys.argv[sys.argv.index('--prof')]

    try:
        test=sys.argv[sys.argv.index("-r")+1]
    except (IndexError, ValueError):
        unittest.main()
    else:
        tc = RDFDomTestCase(test)
        tc.setUp()
        testfunc = getattr(tc, test)
        if profile:
            profilerRun(test, testfunc)
        else:
            testfunc() #run test

