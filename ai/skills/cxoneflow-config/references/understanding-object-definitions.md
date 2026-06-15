# Object Definitions

Object types are used when a configuration element can be referenced multiple times
using YAML anchors.

An object definition will have a type definition in the instructions read for this skill.  Objects of different types
are not interchangeable.  

When defining object definitions in YAML, they must be generated as follows:

* Each object type is named with the element name for which the object is to replace with YAML anchor references.  For example,
  the object of type `cxone` replaces the YAML element named `cxone`.

* Each object definition will have a `purpose` that may be defined by the user.  If the user does not explicitly define an object's
  purpose, the purpose defaults to `default`.

* Object definitions of the same type must have a unique `purpose`.

* If one object of a type is defined, the purpose will be considered the default object definition used by elements
  that are configured with an object of the object type.

* Each object definition makes a level 0 YAML element with an element named with the object type name followed by
  an underscore and an incremental number corresponding to the index of the definition. Examples:
    * Elements named `amqp_1`, `amqp_2`, etc. for an object of type `amqp`.
    * Elements named `cxone_1`, `cxone_2`, etc. for an object of type `cxone`.

* The value of the object definition YAML element will be a YAML anchor that is an ampersand containing the object
  type name appended with an underscore followed by the object's purpose.  Examples:
    * A YAML element with an anchor `amqp_1: &amqp_default` for the default object of type `amqp` with the purpose `default`.
    * A YAML element with an anchor `cxone_1: &cxone_default` for the default object of type `cxone` with the purpose `default`.
    * A YAML element with an anchor `cxone_1: &cxone_prod` for the default object of type `cxone` with the purpose `prod`.
    * A YAML element with an anchor `cxone_2: &cxone_stage` for the default object of type `cxone` with the purpose `stage`
      that appears in the same YAML file as the object `cxone_prod` object.

## Object Definition Form

Each object definition has the element name of the object at level 1 indented from the level 0 object definition.

The following example is an object definition for a `cxone` type object.

```
cxone_1: &cxone_default
  cxone:
    tenant: mytenant
    api-endpoint: US
    iam-endpoint: US
    api-key: api-key.txt
```

## Object Element Names

The following YAML element names are to be considered objects:

* `cxone`
* `amqp`
* `connection`
* `scan-config`
* `scan-agent`
* `feedback`
* `kickoff`
* `proxies`
* `project-groups`


## Minimizing Object Definitions

When it is observed that object definitions are redundant in content, collapse the object
definitions such that the most minimal number of object definitions are created.
