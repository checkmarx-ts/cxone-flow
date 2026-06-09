---
name: cxoneflow-config
description: Generates a YAML configuration file for CxOneFlow.
---


# CxOneFlow YAML Configuration

This skill generates a YAML configuration file for CxOneFlow.  CxOneFlow orchestrates scans
of code from multiple SCM repositories in Checkmarx One.

Reference `references/understanding-cxoneflow-basics.md` to understand terms and concepts
related to CxOneFlow.

Reference `references/understanding-field-specs.md` for common field specifications used when
generating the YAML file.

Reference `references/understanding-object-definitions.md` for forming object definitions.

## Read the Manual

Reference `references/manual/*` for the complete CxOneFlow manual.  The section `YAML Configuration Elements` describes
the configuration element.  Tables in the documentation explain the indentation level of each element as well as
if the element is optional or required.

Elements noted as "required" must be assigned a value under the following conditions:

* The element is at the root of the YAML configuration file (thus no parent YAML element).
* The element has an optional parent YAML element that was selected to be used in the YAML configuration output.
  For example, the `allowed-agent-tags` element is required only if the parent element `scan-agent` is selected for
  output in the YAML configuration file.

Reference `references/manual-clarifications.md` for any clarifications about interpreting manual contents.

The version of CxOneFlow where this skill applies can be found in `references/manual/version.tex`.  The user should be advised
that the YAML configuration skill should be assumed to be compatible only with this version of CxOneFlow.

## Primary Use-Case
* This is to generate a complete YAML configuration file; do not infer other uses or purposes.
* Anything not explicitly configured by the definition here can be assumed to be configured using another method not defined here.
* The levels will be defined relative to level 0 where each level is indented by 2 spaces multiplied by the level.
* You must ask questions about values for required elements that the user must provide before the YAML can be generated.
* When asking questions about values for required elements, describe the elements to the user.
* Do not ask for clarification about including optional elements.
* Do not suggest additional steps for configuration beyond what is explained here.
* Do not infer, offer, or use additional requirements for elements from external documentation.
* If an element is optional, assume that the user does not want to supply a value for the option unless explicitly stated by the user.

At the start of a session to generate the YAML configuration you must:

* Explain that a complete manual is available in the CxOneFlow release artifacts found at URL "https://github.com/checkmarx-ts/cxone-flow/releases/latest".
* Explain that the user will be prompted only for required configuration options.
* Explain that the user can ask what optional configuration elements are available.

## YAML File Generation

Before generating a YAML configuration file:

* You MUST ensure that the YAML file contains a complete and valid configuration.

* You MUST ensure that all required elements selected for inclusion in the YAML output have a value supplied by the user or
  uses the default object definition for the element's object type.
