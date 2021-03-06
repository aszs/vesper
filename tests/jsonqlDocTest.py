#:copyright: Copyright 2009-2010 by the Vesper team, see AUTHORS.
#:license: Dual licenced under the GPL or Apache2 licences, see LICENSE.
'''
Table Of Contents - jsonQL Reference
    Basic Grammar and Processing Model (note reserved words are not case-sensitive)
    Construct Patterns
        Abbreviated properties
        constructing arrays
        constructing simple values
        Property Names and id
        Property wildcard ("*")
        "forcelist" syntax
        optional properties and Null values
        Sub-queries (nested constructs)
    Datatypes
      Value types
      Lists, list values, and multiple values
      null values
      object references
         distinct from string/value representation
         anonymous objects (object as value)
    Filtering (WHERE clause)
      constant queries
    Joins    
        labels
        filter set
        inner joins
        maybe (outer joins)
        uncorrelated references (cross joins)
        follow() (recursive joins)
    Expressions and functions
        filter vs. construct context
        Type coercion
        Built-in Functions
    ORDER BY
    GROUP BY and aggregate Functions
        Built-in aggregate functions
    output modifiers
        mergeall
        limit and offset
        depth
    Bind variables
    namemap
'''

import sys
sys.path.append('.')
from jqltester import *
import jqltester
t = Suite()
skip = Suite()

#restore defaults
jqltester.nameMap = {}
t.useSerializer = True
###################################
########### basic tests ###########
###################################

'''
The processing model for jsonQL is closely follows the relational algebra of SQL. First, any specified :ref:`filterset <filter>` are used to select objects in the store. Then each object is projected onto a row whose columns consist of properties of the object that were referenced by query. If a query has multiple filters, the resulting rows will be joined together join conditions or cartesian product if the 

After this, the "construct" phase

multi-valued...

terminology: 

construct
rows

mention "duck typing" in rapid development section
'''

t.group = 'intro'

t % '''
jsonQL Reference 
~~~~~~~~~~~~~~~~

jsonQL is a language for querying data that can be represented in JSON. Abstractly, a jsonQL query operates on collection of JSON objects that conform to :doc:`pjson` semantics. More concretely, jsonQL works with a Vesper datastore, which provides a logical mapping between objects in a backend datastore to a collection of JSON objects (for example, each object might correspond to a row in table, with a property for each column). A jsonQL query operates on that mapping in a manner similar to a SQL query except that instead of returning rows it returns JSON data structures based on the pattern specified in the query.
'''

t.model = mainmodel = jqltester.getExampleModel()

t % '''
Unless otherwise specified, the example queries here are based on the example datastore found in the :doc:`tutorial`. You can cut and paste or you can run the admin tool on the sample store. 
'''

t % printmodel(t.model)

t % '''

Basic Grammar
=============

Below is simplifed representation of the JQL grammar (the formal grammar can be found :doc:`here <grammar>`). This reference guide will walk through each element of language and provide sample queries illustrating each feature of the language. The queries and sample results are based on the sample json used by the [tutorial] (which, btw, might be a better place to start learning about JQL). 

A jsonQL query consists of a "construct pattern" that describes the JSON output, which can be any JSON type: an object, an array or a simple value like a string. The syntax for jsonQL construct patterns is:

.. productionlist::
 query  : `constructobject` 
        :| `constructarray` 
        :| `constructvalue`
 constructobject : "{" [`label`]
                 :    (`objectitem` | `abbreviateditem` [","])+ 
                 :     [`query_criteria`] 
                 :  "}"
 constructarray  : "[" [`label`]
                 :  (`propertyvalue` [","])+ [`query_criteria`] 
                 : "]"
 constructvalue  : "(" 
                 :    `expression` [`query_criteria`] 
                 : ")"
 objectitem      :  `expression` ":" ["["] ["omitnull"] ["maybe"] `propertyvalue` ["]"]
 propertyvalue   : `expression` | "*" | `nestedconstruct`
 nestedconstruct : `constructarray` | `constructobject`
 abbreviateditem : "ID" | "*" | ["["] ["omitnull"] ["maybe"] `propertyname` ["]"]
 propertyname    : NAME | "<" CHAR+ ">"
 query_criteria  : ["WHERE" `expression`]
                 : ["GROUP BY" (`expression`[","])+]
                 : ["ORDER BY" (`expression` ["ASC"|"DESC"][","])+]
                 : ["LIMIT" number]
                 : ["OFFSET" number]
                 : ["DEPTH" number]
                 : ["MERGEALL"]
                 : ["NAMEMAP" "=" `namemapdict`]
 namemapdict     : "{" [((NAME | STRING) ":" (STRING | `namemapdict`) ","?)+] "}"

The syntax for jsonQL expressions is:

.. productionlist::                 
 expression : `expression` "and" `expression`
            : | `expression` "or" `expression`
            : | "maybe" `expression`
            : | "not" `expression`
            : | `expression` `operator` `expression`
            : | `filterset`
            : | `atom`
            : | "(" `expression` ")"
 operator   : "+" | "-" | "*" | "/" | "%" | "=" | "=="
            : | "<" | "<=" | ">" | "=>" | ["not"] "in"  
 filterset : "{" [`label`] `expression` "}"
 atom       : `label` | `bindvar` | `constant` | `objectreference`
            : | `functioncall` | `propertyreference`
 label      : "?"NAME
 bindvar    : ":"NAME
 objectreference : "@"NAME | "@<" CHAR+ ">"
 propertyreference : [`label`"."]`propertyname`["."`propertyname`]+
 functioncall : NAME([`expression`[","]]+ [NAME"="`expression`[","]]+)
 constant : STRING | NUMBER | "true" | "false" | "null"

Construct Patterns
==================

There are three top level constructions depending on whether you want to construct results as JSON objects (dictionaries), arrays (lists) or simple values (such as a string or number).

A jsonQL query consists of a pattern describes a JSON object (dictionary), a list (array) or simple value -- executing query will construct a list of objects that match the pattern. This example returns a list of all the objects that have properties named "displayname" and "type":

'''

t('''{ 
    "displayname" : displayname,
    "type" : type
    }
''', [
        {
            "displayname": "abbey aardvark",
            "type": "user"            
        }, 
        {
            "displayname": "billy billygoat",
            "type": "user"            
        }
    ]
)

t % '''
Both the property name and value are expressions. In this example, the property names is simply string constants while the property value are property references. In the next example, the property name is the object id and property value is a
more complex expression. It uses the MERGEALL option to return a single dictionary that is a merge of the results.
'''

t("""{
  id : upper(displayname)
  MERGEALL 
}""",
 [{'@user:1': "ABBEY AARDVARK", '@user:2': "BILLY BILLYGOAT"}]
)

t %'''
Abbreviated properties: :token:`objectitem`
-------------------------------------------
When a single property name appears instead of a name-value pair, it is 
treated as a name-value pair where the name is the name of the property and 
the value is a reference to the property. So the following example is 
equivalent to the first query: 
'''
t("{ displayname, type }", [
        {
            "displayname": "abbey aardvark",
            "type": "user"            
        }, 
        {
            "displayname": "billy billygoat",
            "type": "user"            
        }
    ]
)

t%'''
:token:`constructarray`
-----------------------
You can also construct results as arrays (lists) instead of objects. This query selects the same objects but it formats each result as a list not an object.
'''

t("[displayname, type]", [    
    ['abbey aardvark', "user"], ['billy billygoat', "user"]
    ]
)

t%'''
:token:`constructvalue`
-----------------------

You can select simple values (strings or numbers) by wrapping an :token:`expression` in parentheses. For example:
'''

t("(displayname)",
[
    "abbey aardvark", 
    "billy billygoat"
])

t % '''
Property Names and `id`
-----------------------

Name tokens not used elsewhere in the grammar are treated as a reference to object properties.
You can specify properties whose name match reserved keywords or have illegal characters by wrapping the property name with "<" and ">". For example, `<where>` or `<a property with spaces>`.

`id` is a reserved name that always refers to the id of the object, not a property named "id".
Such a property can written as `<id>`.
'''


t("{ 'key' : id, <id>, <a property with spaces>}",
[{'a property with spaces': 'this property name has spaces',  
  'id': 'a property named id',
  'key': '@1'}],
  model = [
  {
  "key" : "1",
  "namemap" : { "id" : "key"},
  "id" : "a property named id",
  "a property with spaces" : "this property name has spaces"
  }
  ] 
)

t%'''
Property wildcard ('*')
-----------------------
The "*" will expand to all properties defined for the object. For example, this query retrieves all objects in the store:
'''
t("{*}", [{'author': '@user:2',
  'contents': 'a comment',
  'id': '@comment1',
  'parent': '@post1',
  'type': 'comment'},
 {'displayname': 'abbey aardvark',
  'email': ['abbey@aardvark.com', 'abbey_aardvark@gmail.com'],
  'id': '@user:1',
  'type': 'user'},
 {'id': '@post1', 'author': '@user:1', 'contents': 'a post', 'type': 'post'},
 {'author': '@user:1',
  'contents': 'a reply',
  'id': '@comment2',
  'parent': '@comment1',
  'type': 'comment'},
 {'author': '@user:1',
  'contents': 'different parent',
  'id': '@comment3',
  'parent': '@comment4',
  'type': 'comment'},
 {'displayname': 'billy billygoat', 'id': '@user:2', 'type': 'user'}]
)


listModel = modelFromJson([
{ "id" : "1",
  "a_list" : ["a", "b"]
},
{ "id" : "1",
  "a_list" : "c"
},
{ "id" : "1",
  "a_list" : None,
  "mixed" : ['a', 'b']
},
{ "id" : "2",
  "mixed" : "c"
},
{ "id" : "3",
  "mixed" : None
}
], checkForDuplicateIds=False)

t % '''
"forcelist" syntax
------------------
You can use wrap the property value with brackets to force the value of a property to always be a list, even when the value just as one value or is `null`. If the value is `null`, an empty list (`[]`) will be used. For example, compare the results of the following two examples which are identical except for the second one's use of "forcelist":
'''

t("{ id, mixed }",
[{'id': '@1', 'mixed': ['a', 'b']},
 {'id': '@3', 'mixed': None},
 {'id': '@2', 'mixed': 'c'}]
,model = listModel
)

t % '''

'''

t("{ id, [mixed] }",
[{'id': '@1', 'mixed': ['a', 'b']},
 {'id': '@3', 'mixed': []},
 {'id': '@2', 'mixed': ['c']}]
,model = listModel
)

t%'''
Null values and optional properties
-----------------------------------

results will only include objects that contain the property referenced in the construct list,
For example, the next example just returns one object because only one has a both a displayname and auth property.
'''
t('{displayname, email}',
[{ 'displayname': 'abbey aardvark',
   'email' : [ 
    'abbey@aardvark.com',
    'abbey_aardvark@gmail.com'
   ]  
  }]
)

t%'''
If property references are modified "maybe" before them then objects without that property will be included in the result. For example:
'''
t('{displayname, maybe email}',
[{ 'displayname': 'abbey aardvark',
   'email' : [ 
    'abbey@aardvark.com',
    'abbey_aardvark@gmail.com'
   ]  
  },  
 {'displayname': 'billy billygoat',
 'email': None}]
)

t % '''
This query still specifies that "auth" property appears in every object in the result -- objects that doesn't have a "auth" property defined have that property value set to null. If you do not want the property included in that case, you can use the the `OMITNULL` modifier instead:
''' 
t('{displayname, omitnull maybe email}',
[{ 'displayname': 'abbey aardvark',
   'email' : [ 
    'abbey@aardvark.com',
    'abbey_aardvark@gmail.com'
   ]  
  },  
 {'displayname': 'billy billygoat'}]
)

t % '''
The above examples illustrate using MAYBE and OMITNULL on appreviated properties. 
Specifically `maybe property` is an abbreviation for  `'property' : maybe property`
and `omitnull property` is an abbreviation for `'property' : omitnull property`.

`omitnull` must appear before the property name and omits the property whenever its value evaluates to null.
For example, here's a silly query that specifies a "nullproperty" property with a constant value
but it will never be included in the result because of the "omitnull".
'''

t('{displayname, "nullproperty" : omitnull null}',
[{ 'displayname': 'abbey aardvark'},
 { 'displayname': 'billy billygoat'}]
)

t%'''
The "forcelist" syntax can be combined with `MAYBE` or `OMITNULL`. For example:
'''
    
t('{displayname, [maybe email]}',
[{ 'displayname': 'abbey aardvark',
   'email' : [ 
    'abbey@aardvark.com',
    'abbey_aardvark@gmail.com'
   ]  
  },  
 {'displayname': 'billy billygoat',
 'email': []
 }]
)

t%'''
Sub-queries (nested constructs)
-------------------------------

The value of a property or array item can be another query instead of an :ref:`expression`. These sub-query can construct objects or arrays (:token:`constructobject` or a :token:`constructarray`) -- :token:`constructvalue` queries are not allowed as sub-queries.

If the sub-query doesn't have a :ref:`filter` associated with it, the sub-query will be  evaluated in the context of the parent object. For example:
'''

t%'''
If the sub-query's filter has references to the outer query (via :ref:`labels`) the filter will be joined with the outer query and it will be evaluated using the rows from the resulting join. For example:
'''

t%'''
Otherwise, the sub-query will be evaluated independently for each result of the outer query. For example:
'''

t%'''
Data Types
==========

A jsonQL implementation supports at least the data types defined by JSON and may support additional data types if the underlying datastore supports them.

The JSON data types are: (unicode) strings, (floating point) numbers, booleans (true and false) and null. Limits such max string length or numeric range and precision and semantics such as numeric overflow behavior are not specified by jsonQL, they will be dependent on the underlying datastore and implementation language. Most database support richer basic basic data types, for example integer, floating point and decimal, the implementation is responsible for appropriate promotion. 

The values of JSON data types can be expressed in a query as literals that match the JSON syntax. Datastore-specific data type values can be expressed using datastore-specific query functions which construct or convert its arguments, for example, date functions. 

They will be serialized as pjson. If the data type is compatible with JSON type it may converted (for example, from exact precision decimal type to JSON's floating point number) depending on the fidelity needed. In addition, if a :ref:`NAMEMAP` is specified in the query customize the serialization. 

Implicit type conversion, by default, is conversion is lenient [example] but the underlying datastore might be string. 

.. question: should there by a strict mode so implementation matches underlying store?

'''

t%'''
null handling
-------------

Unlike sql, null value are treated as distinct values, i.e. "null = null" evaluates to true and "null != null" evaluates to false. Operators and functions generally follow SQL: if one of the operands or arguments is null the result is null. 

footnote: Follow SQL for functions and operators: systems that don't follow these null semantics, generally don't support functions (most NO-SQL) or don't support nulls at all (SPARQL). 
Also, unlike SQL null equality, these semantics is generally intuitive.

Aggregate functions, for example, `count()` ignores null values.  

null < 0 so null go first with order by. 
'''

t.group = 'nulls'

nullModel = t.model = modelFromJson([
{ "id" : "1",
  "value" : None
},
{ "id" : "2",
  "value" : ""
},
{ "id" : "3",
  "value" : True
},
{ "id" : "4",
   "notvalue" : "a"
},
])

#XXX weird syntax error but not with t('[null > 0, null < 0]')
#t('[null < 0, null > 0]')

t("[null=null, null!=null, null=0, null='', 1+null, trim(null), null > 0, null < 0]",
[[True, False, False, False, None, None, False, True]])

t("{id, value where value = null}", [{'id':'@1', "value" : None}])

t("{id, value where value != null}",
[{'id': '@3', 'value': True}, {'id': '@2', 'value': ''}])

t%'''
pseudo-value types
------------------

matches value in the list not the list itself. The data-store may support data types that is serialized as a JSON array, the semantics will not apply. [Example]

order may not be preserved.

Objects without (public) unique identifiers can be treated as value types; 
they may not be queried. Note the implementation may store these as object and even provide (for example, forUpdate).

'''


#mysql's null-safe equal: <=>
#postgres null-safe not equal: IS DISTINCT FROM

t.group = 'lists'

t%'''
Multiple values and lists
-------------------------
* list construction -- multiple values are represented as lists

Note that the actually semantics of inserting pjson depends on the data store it is being inserted into. For example, 
does inserted a property that already exists on an object might add a new value or replace the current one.
'''

t("{ id, a_list }",
[{'a_list': ['a', 'b', 'c', None], 'id': '@1'}]
,model = listModel
)

t%'''
object references and anonymous objects
---------------------------------------

If an object is anonymous it will be expanded, otherwise an object reference object will be output. This behavior can be overridden using the `DEPTH` directive, which will force object references to be expanded, even if objects are duplicated. 

When a top-level (not embeddd) object is added to a data store without an id it is assigned an autogenerated id (cf. pjson docs). Embedded objects without ids are private and can not be referenced. [what about references amongst themselves?] Filters will not match embedded objects unless referenced through a property. [this implies no need to generate a join -- but what if the property can have a reference to both public and private -- need to double filtering?]
'''

t%'''
Filtering (the WHERE clause)
==============================

The `where` clause select which objects should appear in the result set. 

In addition, if the construct clause references a property whose 
values are filtered, only those filters will be included in the result.


In other words, results are grouped by the object id. 

value = 1 and value = 2
value in (1, 2)

* property references in construct
* matching lists 
* matching datatypes
'''

t%'''
all or nothing queries
----------------------

'''

t.group = 'joins'
t.model = mainmodel 

t%'''
Object References and Joins
===========================

labels
------

You can create a reference to an object creating object labels, which look this this syntax: `?identifier`. 

By declaring the variable 

Once an objected labels, you can create joins by referencing that label in an expression.

This is example, value of the contains property will be any object that
'''

t('''
    { ?post 
    *,
    'comments' : { * where parent = ?post}
    where type = 'post'
    }
''')

t%'''
filter sets
--------------

When a filter expression is surrounded by braces (`{` and `}`) the filter is applied 
separately from the rest of the expression, and is evaluated as an object reference
to the object that met that criteria. These object references have the same semantics 
as label references. The object references can optionally be labeled and are typically 
used to create joins.

Note that a filter expression like `{id = ?foo}` is logically equivalent to labeling the group `?foo`.
'''

t('''
{ * 
where type = 'comment' and parent = { type = 'post'} 
}
''')

t('''
{ * 
where type = 'comment' and parent = ?post and {?post type = 'post'} 
}
''')

t('''
{ * 
where type = 'comment' and parent = ?post and { id = ?post and type = 'post'} 
}
''')

#XXX document:
# When evaluating, join expressions are replaced with a label reference to that join.
# These labels evaluate to the object id of the object except when evaluating as a boolean, 
# in that case it returns true if the object id exists (e.g. a label to an object 
#whose id's value was 0 would still evaluate as true)
#Note that following these rules, a join expression at the root of the where filter expression 
#(e.g. "where ({ a=1 })") evaluates to true if there exists an object with "a = 1"

t%'''
joins
------



'''

t%'''
`maybe` expressions (outer joins)
---------------------------------

The "MAYBE" operator indicates that the expression it modifies is an optional part of the filter set. 
MAYBE can modify property references and join conditions; it is an error to modify any other expression.
When "maybe" modifies a property reference it indicates that the existence of a property not required. When "maybe" modifies a join condition (an expression that joins two filter sets together) if the condition does not match any objects, any references to the missing objects' id or properties will replaced with nulls (this is know as an "outer join"). 
'''

t%'''
For example, object don't

#property reference in filter prop = maybe ?label and ?label.type = 'type'

#can also appear in the construction: { maybe foo}

'''

t('''
{
prop1, maybe prop2
}
''')

'''
One `maybe` operator is enough -- the "non-maybe" reference doesn't override that.

#example: multiple references

#note precedence: maybe prop = null will give error "maybe can not be used on a filter that is not a join condition", need to use (maybe prop) = null
'''

'''
outer join example: maybe foo = ?bar

Note that maybe foo = ?bar still requires 'foo' property to exist: the precedence rules imply maybe (foo = ?bar). To make the foo property optional, use maybe (maybe foo) = ?bar or, more readably, maybe foo and maybe foo = ?bar

'''

'''
A filter expression that references an MAYBE-modified property will evaluated with null as the value for the missing property. That means an expression like "value = null" will match objects that don't have that property. For example:
'''

t("{id, maybe value where value = null}", 
[{'id':'@1', "value" : None}, {'id':'@4', "value" : None}]
,model=nullModel)

'''
Conversely, a filter expression that does not match null value on a MAYBE-modified property reference are not useful since the filter not match any object that don't have that property. For example:
'''

t("{id, maybe value where value != null}",
[{'id': '@3', 'value': True}, {'id': '@2', 'value': ''}]
,model=nullModel)

'or:'

t("{id, maybe value where value = ''}",
[{ "id" : "@2",
  "value" : ""
}]
,model=nullModel)

#filter
t('''
{
prop1, prop2 where (maybe prop2 = 'foo')
}
''', ast='error')

#filter
t('''
{
prop1, prop2, prop3 where maybe prop2 = prop3
}
''', ast='error')

#what prop2 = null and prop3 doesn't exist? match on that object? yes
t('''
{
prop1, prop2, prop3 where prop2 = maybe prop3
}
''')

#XXX allow projects like ?blah.prop3 as an abbreviated prop?
skip('''
{
prop1, prop2, ?blah.prop3 where maybe { ?blah foo = 1 and bar = 2 }
}
''')

#XXX the use of maybe here doesn't make sense, should trigger error 
skip('''{ * where 
 maybe {?a foo = 1} and maybe {?b bar = 2} and ?a = ?b
}''')

'''
Design note: maybe on a filter that isn't a join condition is useless because that expression will match every object. The only possible example I could think of was be a filter had some sort of side effect (e.g. a function call) but don't think its worth the trouble to support that. 

jsonql doesn't currently allow MAYBE to operate on a filter-set or on a label but allowing this would enable something that isn't possible now: the ability to do an outer join on uncorrelated filter-sets. But full support of that syntax would require support for right outer and full outer joins, which isn't desirable.
'''

t%'''
uncorrelated references (cross joins)
-------------------------------------
'''

t%'''
the follow() function (recursive joins)
---------------------------------------
'''

#XXX { * where id in rfollow(...) } doesn't work, need explicit label
t('''
    { ?post 
    *,
    'comments' : {?comment * where ?comment in rfollow(?post, parent, true)}
    where type = 'post'
    }
''',
[{'author': '@user:1',
  'comments': [{'author': '@user:2',
                'contents': 'a comment',
                'id': '@comment1',
                'parent': '@post1',
                'type': 'comment'},
               {'author': '@user:1',
                'contents': 'a reply',
                'id': '@comment2',
                'parent': '@comment1',
                'type': 'comment'}],
  'contents': 'a post',
  'id': '@post1',
  'type': 'post'}]
)

t % '''
Expressions
===========

Expressions can be evaluated in two contexts: when they appear inside the where clause and when they appear inside the construction
WHAT ABOUT: order by, group by ?

If an expression contains a property reference whose value a list and the expression doesn't contain any :ref:`aggregate functions', the expression will be evaluated for each item in that list, resulting in a list. If the expression contains more than one property reference, the expression will be evaluated on each tuple obtained from a cartesian product of the list values, using an order based on the depth-first appearance of the property references.

Operator Precedence
-------------------

Follows SQL, from highest to lowest. 

( )
.
unary + / unary - (right)
* / %
+ -
< <= > >= = !=
in 
not
maybe
and
or

Operators with equal precedence are evaluated from left-to-right, except for the unary operator, which evaluate from right-to-left.

Type coercion
-------------

Built-in functions
------------------
'''

t%'''
Sorting the results: ORDER BY 
=============================

'''

t%'''
Groupby and aggregate Functions
===============================

If a "group by" clause is not specified, the aggregate function will be apply

Built-in aggregate functions
----------------------------

count, min, max, sum, avg follow standard SQL semantics with regard to null handling, 
*total* follow the semantics sqllite's *total*, described here: http://www.sqlite.org/lang_aggfunc.html

'''

t%'''
output modifiers
================

MERGEALL
--------

DEPTH
-----

DEPTH may result in duplicate objects being constructed if there are multiple reference to the same object, including circular references [hmmm... better not choose a arbitrary to number to expand all like DEPTH 1000].
Objects no properties are not serialized as objects, they will remain an object reference.

Note: expand a particular object, use ... or use DEPTH in a nested construct.

LIMIT and OFFSET
----------------

LIMIT and OFFSET are applied to the final resultset, after any GROUP BY and ORDER BY operations, but before the MERGEALL operation.
'''

t%'''
Bind variables
==============
'''

t%'''
NAMEMAP
========

The value of a NAMEMAP declaration matches pjson's namemap and is used both when parsing the query and when serializing the resultset. 

The namemap applies to the construct pattern it appears in and in any nested constructs. 
If a nested construct has a NAMEMAP described, the effective namemap is the merger of this namemap with the effective parent namemap, as specified for pjson.
'''
#XXX Renaming properties are only used when serializing

t.group = 'footnotes'
'''
.. rubric:: Footnotes

.. [#f1] blah blah
'''


t%'''
.. raw:: html

    <style>
    .example-plaintext { position:absolute; z-index: 2; background-color: lightgray;}
    .close-example-plaintext { float:right; 
      padding-right: 3px;     
      font-size: .83em;
      line-height: 0.7em;
      vertical-align: baseline;
    }
    .close-example-plaintext:hover { color: #CA7900; cursor: pointer; }
    .toolbar { background-color: lightgray; float:right; 
        border:1px solid;
        padding: 1px;
        text-decoration:underline;
    }
    .toolbar:hover { color: #CA7900; cursor: pointer; }
    </style>
    <script>
    $().ready(function(){
      $('.example-plaintext ~ .highlight-python pre').prepend("<span class='toolbar'>Copy Code</span");
      $('.toolbar').click(function() {
        $(this).parents('.highlight-python').prev('.example-plaintext:last')
          .slideDown('fast').find('textarea').focus();
      });
      $('.close-example-plaintext').click(function() { 
            $(this).parents('.example-plaintext').slideUp('fast').find('textarea').blur(); 
      });
    });
    </script>   

..  colophon: this doc was generated by "python tests/jsonqlDocTest.py --printdoc > doc/source/spec.rst"
'''

import unittest
class JQLTestCase(unittest.TestCase):
    def testAll(self):
        main(t, ['--quiet'])

if __name__ == "__main__":
    main(t) #invoke jqltest.main()